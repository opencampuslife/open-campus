from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from app.db.connection import get_conn
from app.modules.campus.shared import audit, school_id


def export_module_csv(identity: dict[str, Any], module: str, project_root: Path) -> dict[str, Any]:
    school = school_id(identity)
    queries: dict[str, tuple[str, list[str]]] = {
        "scores": (
            """
            SELECT sb.exam_name, sb.subject, se.student_no, se.student_name, se.score, se.review_status
            FROM score_entries se JOIN score_batches sb ON sb.batch_id = se.batch_id
            WHERE se.school_id = %s ORDER BY sb.exam_name, sb.subject, se.student_no
            """,
            ["exam_name", "subject", "student_no", "student_name", "score", "review_status"],
        ),
        "payments": (
            """
            SELECT pt.title, s.student_no, s.name AS student_name, pr.extracted_amount, pr.status
            FROM payment_records pr JOIN payment_tasks pt ON pt.task_id = pr.task_id
            JOIN students s ON s.student_id = pr.student_id
            WHERE pr.school_id = %s ORDER BY pt.title, s.student_no
            """,
            ["title", "student_no", "student_name", "extracted_amount", "status"],
        ),
        "attendance": (
            """
            SELECT ats.attendance_date, ats.period, s.student_no, s.name AS student_name, ar.status
            FROM attendance_records ar JOIN attendance_sessions ats ON ats.session_id = ar.session_id
            JOIN students s ON s.student_id = ar.student_id
            WHERE ar.school_id = %s ORDER BY ats.attendance_date, ats.period, s.student_no
            """,
            ["attendance_date", "period", "student_no", "student_name", "status"],
        ),
    }
    if module not in queries:
        raise ValueError("UNSUPPORTED_EXPORT_MODULE")
    query, fields = queries[module]
    with get_conn() as conn:
        rows = conn.execute(query, (school,)).fetchall()
    folder = project_root / "data" / "exports" / "campus"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{school}_{module}.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    audit(identity, "campus_export", module, "campus_export.created", {"module": module, "row_count": len(rows)})
    return {"module": module, "rows": len(rows), "file_path": str(path)}
