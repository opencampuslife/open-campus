from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from app.db.connection import get_conn
from app.db.repositories.operation_logs import write_operation_log


def _stable_id(prefix: str, school_id: str, value: str) -> str:
    digest = hashlib.sha256(f"{school_id}:{value}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _mobile_hash(raw: str) -> str | None:
    normalized = "".join(ch for ch in raw if ch.isdigit())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else None


def _read_csv(path: Path | None) -> list[dict[str, str]]:
    if not path:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _require(row: dict[str, str], row_number: int, fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not str(row.get(field, "")).strip()]
    if missing:
        raise ValueError(f"row {row_number}: missing {','.join(missing)}")


def _upsert_class(school_id: str, row: dict[str, str], row_number: int) -> str:
    name = str(row.get("class_name") or row.get("name") or "").strip()
    if not name:
        raise ValueError(f"row {row_number}: missing class_name")
    class_id = _stable_id("CLS", school_id, name)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO classes (class_id, school_id, grade, name)
            VALUES (%(class_id)s, %(school_id)s, %(grade)s, %(name)s)
            ON CONFLICT (class_id) DO UPDATE SET grade = EXCLUDED.grade, name = EXCLUDED.name
            """,
            {
                "class_id": class_id,
                "school_id": school_id,
                "grade": str(row.get("grade") or "未设置").strip(),
                "name": name,
            },
        )
    return class_id


def _class_id_by_name(school_id: str, class_name: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT class_id FROM classes WHERE school_id = %(school_id)s AND name = %(name)s",
            {"school_id": school_id, "name": class_name},
        ).fetchone()
    if not row:
        raise ValueError(f"class not imported: {class_name}")
    return str(row["class_id"])


def _upsert_student(school_id: str, row: dict[str, str], row_number: int) -> str:
    _require(row, row_number, ("student_no", "name", "class_name"))
    student_no = row["student_no"].strip()
    class_id = _class_id_by_name(school_id, row["class_name"].strip())
    student_id = _stable_id("STU", school_id, student_no)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO students (
                student_id, school_id, class_id, name, student_no,
                parent_name, parent_mobile_hash, parent_userid, status
            ) VALUES (
                %(student_id)s, %(school_id)s, %(class_id)s, %(name)s, %(student_no)s,
                %(parent_name)s, %(parent_mobile_hash)s, %(parent_userid)s, 'active'
            )
            ON CONFLICT (student_id) DO UPDATE SET
                class_id = EXCLUDED.class_id, name = EXCLUDED.name,
                parent_name = EXCLUDED.parent_name,
                parent_mobile_hash = EXCLUDED.parent_mobile_hash,
                parent_userid = COALESCE(EXCLUDED.parent_userid, students.parent_userid),
                status = 'active'
            """,
            {
                "student_id": student_id,
                "school_id": school_id,
                "class_id": class_id,
                "name": row["name"].strip(),
                "student_no": student_no,
                "parent_name": str(row.get("parent_name", "")).strip() or None,
                "parent_mobile_hash": _mobile_hash(str(row.get("parent_mobile", ""))),
                "parent_userid": str(row.get("parent_wecom_userid", "")).strip() or None,
            },
        )
    return student_id


def _upsert_teacher(school_id: str, row: dict[str, str], row_number: int) -> str:
    _require(row, row_number, ("name", "wecom_userid", "role"))
    userid = row["wecom_userid"].strip()
    role = row["role"].strip()
    if role not in {"school_admin", "head_teacher", "academic_staff", "logistics_staff", "repair_assignee"}:
        raise ValueError(f"row {row_number}: invalid teacher role {role}")
    class_name = str(row.get("class_name", "")).strip()
    class_id = _class_id_by_name(school_id, class_name) if class_name else None
    user_id = _stable_id("USR", school_id, userid)
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO campus_users (user_id, school_id, wecom_userid, name, role, class_id, status)
            VALUES (%(user_id)s, %(school_id)s, %(wecom_userid)s, %(name)s, %(role)s, %(class_id)s, 'active')
            ON CONFLICT (user_id) DO UPDATE SET
                wecom_userid = EXCLUDED.wecom_userid, name = EXCLUDED.name,
                role = EXCLUDED.role, class_id = EXCLUDED.class_id, status = 'active'
            """,
            {
                "user_id": user_id,
                "school_id": school_id,
                "wecom_userid": userid,
                "name": row["name"].strip(),
                "role": role,
                "class_id": class_id,
            },
        )
        if role == "head_teacher" and class_id:
            conn.execute(
                "UPDATE classes SET head_teacher_id = %(user_id)s WHERE class_id = %(class_id)s",
                {"user_id": user_id, "class_id": class_id},
            )
    return user_id


def _upsert_parent_binding(school_id: str, row: dict[str, str], row_number: int) -> str:
    _require(row, row_number, ("student_no", "parent_wecom_userid"))
    with get_conn() as conn:
        student = conn.execute(
            "SELECT student_id FROM students WHERE school_id = %(school_id)s AND student_no = %(student_no)s",
            {"school_id": school_id, "student_no": row["student_no"].strip()},
        ).fetchone()
        if not student:
            raise ValueError(f"row {row_number}: student not imported {row['student_no'].strip()}")
        conn.execute(
            """
            UPDATE students SET parent_userid = %(parent_userid)s,
                parent_name = COALESCE(%(parent_name)s, parent_name),
                parent_mobile_hash = COALESCE(%(mobile_hash)s, parent_mobile_hash)
            WHERE student_id = %(student_id)s
            """,
            {
                "student_id": student["student_id"],
                "parent_userid": row["parent_wecom_userid"].strip(),
                "parent_name": str(row.get("parent_name", "")).strip() or None,
                "mobile_hash": _mobile_hash(str(row.get("parent_mobile", ""))),
            },
        )
    return str(student["student_id"])


def _import_rows(
    *,
    school_id: str,
    kind: str,
    rows: list[dict[str, str]],
    importer: Callable[[str, dict[str, str], int], str],
) -> tuple[int, list[dict[str, Any]]]:
    imported = 0
    errors: list[dict[str, Any]] = []
    for number, row in enumerate(rows, 2):
        try:
            importer(school_id, row, number)
            imported += 1
        except Exception as exc:
            errors.append({"file": kind, "row": number, "error": str(exc), "data": row})
    return imported, errors


def import_pilot_data(
    *,
    school_id: str,
    classes_path: Path | None,
    students_path: Path | None,
    teachers_path: Path | None,
    parent_bindings_path: Path | None,
    report_path: Path,
) -> dict[str, Any]:
    counts: dict[str, int] = {}
    errors: list[dict[str, Any]] = []
    for kind, path, importer in (
        ("classes", classes_path, _upsert_class),
        ("students", students_path, _upsert_student),
        ("teachers", teachers_path, _upsert_teacher),
        ("parent_bindings", parent_bindings_path, _upsert_parent_binding),
    ):
        counts[kind], import_errors = _import_rows(
            school_id=school_id, kind=kind, rows=_read_csv(path), importer=importer,
        )
        errors.extend(import_errors)
    report = {"ok": not errors, "school_id": school_id, "imported": counts, "errors": errors}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_operation_log(
        school_id=school_id, actor_user_id="pilot_import", biz_type="pilot_import",
        biz_id=school_id, action="pilot_data.imported",
        after={"imported": counts, "error_count": len(errors)},
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--school-id", required=True)
    parser.add_argument("--classes", type=Path)
    parser.add_argument("--students", type=Path)
    parser.add_argument("--teachers", type=Path)
    parser.add_argument("--parent-bindings", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = import_pilot_data(
        school_id=args.school_id,
        classes_path=args.classes,
        students_path=args.students,
        teachers_path=args.teachers,
        parent_bindings_path=args.parent_bindings,
        report_path=args.report,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
