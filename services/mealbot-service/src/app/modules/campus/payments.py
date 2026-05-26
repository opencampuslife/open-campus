from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from app.db.repositories import campus_modules as repo
from app.modules.campus.shared import actor_id, anomaly, audit, entity_id, queue_ocr, schedule_reminder, school_id


def create_task(identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    task = repo.create_payment_task(
        {
            "task_id": entity_id("PAY"),
            "school_id": school_id(identity),
            "class_id": str(payload["class_id"]),
            "title": str(payload["title"]),
            "amount_due": Decimal(str(payload["amount_due"])),
            "deadline_at": payload["deadline_at"],
            "account_note": str(payload.get("account_note", "")),
            "created_by": actor_id(identity),
        }
    )
    audit(identity, "payment_task", task["task_id"], "payment_task.created", {"class_id": task["class_id"]})
    return task


def submit(identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    task = repo.get_payment_task(str(payload["task_id"]))
    if not task or task["school_id"] != school_id(identity):
        raise ValueError("PAYMENT_TASK_NOT_ACCESSIBLE")
    student = repo.get_student(str(payload["student_id"]))
    if not student or student["school_id"] != task["school_id"] or student["class_id"] != task["class_id"]:
        raise ValueError("STUDENT_NOT_IN_PAYMENT_CLASS")
    record = repo.upsert_payment_record(
        {
            "record_id": entity_id("PREC"),
            "school_id": task["school_id"],
            "task_id": task["task_id"],
            "student_id": str(payload["student_id"]),
            "attachment_id": payload.get("attachment_id"),
            "submitted_by": actor_id(identity),
        }
    )
    job = queue_ocr(identity, "payment_extract", record["record_id"], record.get("attachment_id"), payload.get("fixture_extraction"))
    audit(identity, "payment_record", record["record_id"], "payment_record.created", {"task_id": task["task_id"]})
    return {"record": record, "ocr_job": job}


def apply_extraction(identity: dict[str, Any], record_id: str, extracted: dict[str, Any]) -> dict[str, Any]:
    transaction_ref = str(extracted.get("transaction_ref", "")).strip()
    sanitized = {
        "name": str(extracted.get("name", "")),
        "amount": Decimal(str(extracted["amount"])) if extracted.get("amount") not in (None, "") else None,
        "paid_at": extracted.get("paid_at"),
        "transaction_ref_hash": hashlib.sha256(transaction_ref.encode("utf-8")).hexdigest() if transaction_ref else None,
    }
    record = repo.update_payment_extraction(record_id, sanitized)
    if not record:
        raise ValueError("PAYMENT_RECORD_NOT_FOUND")
    task = repo.get_payment_task(record["task_id"])
    if not task:
        raise ValueError("PAYMENT_TASK_NOT_FOUND")
    findings: list[tuple[str, str, str]] = []
    if sanitized["amount"] != task["amount_due"]:
        findings.append(("amount_mismatch", "缴费金额与应缴金额不一致", "high"))
    student = repo.get_student(record["student_id"])
    if sanitized["name"] and student and sanitized["name"] != student["name"]:
        findings.append(("name_mismatch", "付款截图姓名与学生不一致", "medium"))
    anomalies = []
    for finding_type, message, risk in findings:
        anomalies.append(
            repo.create_payment_anomaly(
                {
                    "anomaly_id": entity_id("PA"),
                    "school_id": record["school_id"],
                    "task_id": record["task_id"],
                    "record_id": record_id,
                    "anomaly_type": finding_type,
                    "message": message,
                    "risk_level": risk,
                }
            )
        )
        anomaly(identity, "payment_record", record_id, finding_type, risk, {})
    audit(identity, "payment_record", record_id, "payment_record.ocr_extracted", {"review_required": True, "anomaly_count": len(anomalies)})
    return {"record": record, "anomalies": anomalies}


def confirm_record(identity: dict[str, Any], record_id: str) -> dict[str, Any]:
    record = repo.confirm_payment(record_id, actor_id(identity))
    if not record:
        raise ValueError("PAYMENT_NOT_REVIEWABLE")
    audit(identity, "payment_record", record_id, "payment_record.confirmed", {"status": "confirmed"})
    return record


def remind_missing(identity: dict[str, Any], task_id: str) -> dict[str, Any]:
    task = repo.get_payment_task(task_id)
    if not task or task["school_id"] != school_id(identity):
        raise ValueError("PAYMENT_TASK_NOT_ACCESSIBLE")
    missing = repo.list_payment_missing(task_id)
    for student in missing:
        schedule_reminder(
            identity,
            biz_type="payment_missing",
            biz_id=f"{task_id}:{student['student_id']}",
            receiver_type="parent",
            receiver_id=str(student.get("parent_userid") or student["student_id"]),
            template_id="payment_missing_reminder",
            payload={"task_id": task_id, "student_id": student["student_id"], "title": task["title"]},
            unique_suffix="first",
        )
    audit(identity, "payment_task", task_id, "payment_missing.reminded", {"missing_count": len(missing)})
    return {"task": task, "missing": missing, "reminders_created": len(missing)}
