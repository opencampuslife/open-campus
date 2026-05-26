from __future__ import annotations

import base64
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

MEALBOT_SRC = Path(__file__).resolve().parents[2] / "mealbot-service" / "src"
if str(MEALBOT_SRC) not in sys.path:
    sys.path.insert(0, str(MEALBOT_SRC))

from app.db.repositories import attachments as attachment_repo  # noqa: E402
from app.db.repositories import campus_modules as module_repo  # noqa: E402
from app.modules.campus import attendance, automation, leaves, materials, payments, reports, scores  # noqa: E402
from app.storage.local import save_upload_bytes  # noqa: E402

ADMIN_ROLES = {"admin", "super_admin", "school_admin"}
ACADEMIC_ROLES = ADMIN_ROLES | {"academic_admin", "academic_staff"}
TEACHER_ROLES = ACADEMIC_ROLES | {"head_teacher", "teacher"}
FINANCE_ROLES = ADMIN_ROLES | {"finance"}
PARENT_ROLE = "parent_or_student_h5"


def _safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe(item) for item in value]
    return value


def _school(identity: dict[str, Any]) -> str:
    value = str(identity.get("school_id") or identity.get("campus") or "")
    if not value or value == "all":
        raise ValueError("school_id is required in identity")
    return value


def _require_role(identity: dict[str, Any], roles: set[str]) -> None:
    if str(identity.get("role")) not in roles:
        raise ValueError("FORBIDDEN")


def _require_class(identity: dict[str, Any], class_id: str) -> None:
    if str(identity.get("role")) in ADMIN_ROLES | {"academic_admin", "academic_staff", "finance"}:
        return
    allowed = identity.get("class_ids") or [identity.get("class_id")]
    if class_id not in {str(value) for value in allowed if value}:
        raise ValueError("CLASS_NOT_ACCESSIBLE")


def _require_student(identity: dict[str, Any], student_id: str) -> None:
    if str(identity.get("role")) != PARENT_ROLE:
        return
    if str(identity.get("student_id", "")) != student_id:
        raise ValueError("STUDENT_NOT_ACCESSIBLE")


def _require_student_class(identity: dict[str, Any], student_id: str, class_id: str) -> None:
    _require_student(identity, student_id)
    student = module_repo.get_student(student_id)
    if not student or student["school_id"] != _school(identity) or student["class_id"] != class_id:
        raise ValueError("STUDENT_CLASS_NOT_ACCESSIBLE")


def _attachment_for_request(payload: dict[str, Any], identity: dict[str, Any]) -> str | None:
    attachment_id = str(payload.get("attachment_id") or "").strip()
    if attachment_id:
        item = attachment_repo.get_attachment(attachment_id)
        if not item or item["school_id"] != _school(identity):
            raise ValueError("ATTACHMENT_NOT_ACCESSIBLE")
        if identity.get("role") == PARENT_ROLE:
            owner = str(identity.get("wecom_userid") or identity.get("user_id") or "")
            if item.get("created_by_wecom_userid") != owner:
                raise ValueError("ATTACHMENT_NOT_ACCESSIBLE")
        if item.get("biz_id"):
            raise ValueError("ATTACHMENT_ALREADY_LINKED")
        return attachment_id
    file_bytes = payload.get("file_bytes") or payload.get("photo_bytes")
    if not file_bytes and payload.get("photo_base64"):
        file_bytes = base64.b64decode(str(payload["photo_base64"]))
    if not isinstance(file_bytes, bytes) or not file_bytes:
        return None
    stored = save_upload_bytes(
        file_bytes=file_bytes,
        original_name=str(payload.get("file_filename") or payload.get("photo_filename", "upload.jpg")),
        content_type=str(payload.get("file_content_type") or payload.get("photo_content_type", "image/jpeg")),
        school_id=_school(identity),
    )
    created = attachment_repo.create_attachment(
        {
            "attachment_id": f"ATT-{uuid4().hex[:12]}",
            "school_id": _school(identity),
            "source": "h5_upload",
            "biz_type": None,
            "biz_id": None,
            **stored,
            "created_by_wecom_userid": str(identity.get("wecom_userid") or identity.get("user_id") or ""),
        }
    )
    return str(created["attachment_id"])


def post_collection_task(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, TEACHER_ROLES)
    _require_class(identity, str(payload["class_id"]))
    return _safe({"ok": True, "task": materials.create_task(identity, payload)})


def post_material_submission(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, {PARENT_ROLE} | TEACHER_ROLES)
    _require_student(identity, str(payload["student_id"]))
    enriched = dict(payload)
    if identity.get("role") == PARENT_ROLE:
        enriched.pop("fixture_extraction", None)
    enriched["attachment_id"] = _attachment_for_request(payload, identity)
    result = materials.submit(identity, enriched)
    if enriched["attachment_id"]:
        attachment_repo.link_attachment_to_biz(enriched["attachment_id"], "material_submission", result["submission"]["submission_id"])
    return _safe({"ok": True, **result})


def post_material_missing(task_id: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    del payload
    _require_role(identity, TEACHER_ROLES)
    task = module_repo.get_collection_task(task_id)
    if not task:
        raise ValueError("COLLECTION_TASK_NOT_FOUND")
    _require_class(identity, str(task["class_id"]))
    return _safe({"ok": True, **materials.missing_and_remind(identity, task_id)})


def post_module_leave(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, {PARENT_ROLE} | TEACHER_ROLES)
    _require_student_class(identity, str(payload["student_id"]), str(payload["class_id"]))
    return _safe({"ok": True, "leave": leaves.create_request(identity, payload)})


def post_module_leave_decision(leave_id: str, decision: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, TEACHER_ROLES)
    leave = module_repo.get_leave(leave_id)
    if not leave:
        raise ValueError("LEAVE_NOT_FOUND")
    _require_class(identity, str(leave["class_id"]))
    return _safe({"ok": True, "leave": leaves.decide(identity, leave_id, decision, str(payload.get("note", "")))})


def post_module_leave_return(leave_id: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    del payload
    _require_role(identity, {PARENT_ROLE} | TEACHER_ROLES)
    leave = module_repo.get_leave(leave_id)
    if not leave:
        raise ValueError("LEAVE_NOT_FOUND")
    if identity.get("role") == PARENT_ROLE:
        _require_student(identity, str(leave["student_id"]))
    else:
        _require_class(identity, str(leave["class_id"]))
    return _safe({"ok": True, "leave": leaves.confirm_return(identity, leave_id)})


def post_overdue_returns(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    del payload
    _require_role(identity, ACADEMIC_ROLES)
    return _safe({"ok": True, **leaves.process_overdue_returns(identity)})


def post_score_batch(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, TEACHER_ROLES)
    _require_class(identity, str(payload["class_id"]))
    enriched = dict(payload)
    enriched["attachment_id"] = _attachment_for_request(payload, identity)
    result = scores.create_batch(identity, enriched)
    if enriched["attachment_id"]:
        attachment_repo.link_attachment_to_biz(enriched["attachment_id"], "score_batch", result["batch"]["batch_id"])
    return _safe({"ok": True, **result})


def post_score_confirm(batch_id: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    del payload
    _require_role(identity, ACADEMIC_ROLES)
    return _safe({"ok": True, "batch": scores.confirm_batch(identity, batch_id)})


def post_payment_task(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, FINANCE_ROLES)
    return _safe({"ok": True, "task": payments.create_task(identity, payload)})


def post_payment_record(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, {PARENT_ROLE} | FINANCE_ROLES)
    _require_student(identity, str(payload["student_id"]))
    enriched = dict(payload)
    if identity.get("role") == PARENT_ROLE:
        enriched.pop("fixture_extraction", None)
    enriched["attachment_id"] = _attachment_for_request(payload, identity)
    result = payments.submit(identity, enriched)
    if enriched["attachment_id"]:
        attachment_repo.link_attachment_to_biz(enriched["attachment_id"], "payment_record", result["record"]["record_id"])
    return _safe({"ok": True, **result})


def post_payment_confirm(record_id: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    del payload
    _require_role(identity, FINANCE_ROLES)
    return _safe({"ok": True, "record": payments.confirm_record(identity, record_id)})


def post_payment_missing(task_id: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    del payload
    _require_role(identity, FINANCE_ROLES | {"head_teacher"})
    task = module_repo.get_payment_task(task_id)
    if not task:
        raise ValueError("PAYMENT_TASK_NOT_FOUND")
    _require_class(identity, str(task["class_id"]))
    return _safe({"ok": True, **payments.remind_missing(identity, task_id)})


def post_attendance_session(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, TEACHER_ROLES)
    _require_class(identity, str(payload["class_id"]))
    return _safe({"ok": True, "session": attendance.create_session(identity, payload)})


def post_attendance_records(session_id: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, TEACHER_ROLES)
    session = module_repo.get_attendance_session(session_id)
    if not session:
        raise ValueError("ATTENDANCE_SESSION_NOT_FOUND")
    _require_class(identity, str(session["class_id"]))
    records = payload.get("records")
    if not isinstance(records, list):
        raise ValueError("records must be a list")
    return _safe({"ok": True, **attendance.submit_records(identity, session_id, records)})


def post_process_ocr(payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, ADMIN_ROLES | {"academic_admin", "academic_staff", "finance"})
    return {
        "ok": True,
        **automation.process_ocr_jobs(
            str(payload.get("worker_id", "api_campus_ocr")),
            int(payload.get("limit", 20)),
            _school(identity),
        ),
    }


def get_modules_dashboard(identity: dict[str, Any]) -> dict[str, Any]:
    _require_role(identity, ADMIN_ROLES | {"academic_admin", "academic_staff", "finance", "head_teacher"})
    return _safe({"ok": True, "school_id": _school(identity), "summary": module_repo.dashboard_summary(_school(identity))})


def post_score_rpa_dry_run(batch_id: str, payload: dict[str, Any], identity: dict[str, Any]) -> dict[str, Any]:
    del payload
    _require_role(identity, ACADEMIC_ROLES)
    return _safe({"ok": True, "rpa_job": scores.create_rpa_dry_run(identity, batch_id)})


def post_module_export(payload: dict[str, Any], identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    _require_role(identity, ADMIN_ROLES | {"academic_admin", "academic_staff", "finance"})
    return _safe({"ok": True, "export": reports.export_module_csv(identity, str(payload["module"]), project_root)})
