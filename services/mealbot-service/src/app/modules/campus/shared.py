from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.db.repositories import campus_modules as repo
from app.db.repositories import operation_logs, reminder_tasks


def entity_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


def actor_id(identity: dict[str, Any]) -> str:
    return str(identity.get("user_id") or identity.get("wecom_userid") or "system")


def school_id(identity: dict[str, Any]) -> str:
    value = str(identity.get("school_id") or identity.get("campus") or "")
    if not value or value == "all":
        raise ValueError("school_id is required in identity")
    return value


def audit(identity: dict[str, Any], biz_type: str, biz_id: str, action: str, after: dict[str, Any] | None = None) -> None:
    operation_logs.write_operation_log(
        school_id=school_id(identity),
        actor_user_id=actor_id(identity),
        biz_type=biz_type,
        biz_id=biz_id,
        action=action,
        after=after or {},
    )


def schedule_reminder(
    identity: dict[str, Any],
    *,
    biz_type: str,
    biz_id: str,
    receiver_type: str,
    receiver_id: str,
    template_id: str,
    payload: dict[str, Any],
    scheduled_at: datetime | None = None,
    unique_suffix: str = "",
) -> dict[str, Any] | None:
    return reminder_tasks.create_reminder_task(
        {
            "reminder_id": entity_id("RT"),
            "school_id": school_id(identity),
            "biz_type": biz_type,
            "biz_id": biz_id,
            "receiver_type": receiver_type,
            "receiver_id": receiver_id,
            "channel": "wecom_app_message",
            "template_id": template_id,
            "payload_json": payload,
            "scheduled_at": scheduled_at or datetime.now(timezone.utc),
            "idempotency_key": f"{biz_type}_{biz_id}_{template_id}_{unique_suffix}",
        }
    )


def queue_ocr(identity: dict[str, Any], job_type: str, biz_id: str, attachment_id: str | None, fixture_result: Any = None) -> dict[str, Any]:
    job = repo.create_ocr_job(
        {
            "job_id": entity_id("OCR"),
            "school_id": school_id(identity),
            "job_type": job_type,
            "biz_id": biz_id,
            "attachment_id": attachment_id,
            "input_json": {"fixture_result": fixture_result} if fixture_result is not None else {},
        }
    )
    audit(identity, "ocr_job", job["job_id"], "ocr_job.created", {"job_type": job_type, "biz_id": biz_id})
    return job


def anomaly(identity: dict[str, Any], biz_type: str, biz_id: str, anomaly_type: str, risk_level: str, details: dict[str, Any]) -> dict[str, Any]:
    created = repo.create_anomaly(
        {
            "anomaly_id": entity_id("ANOM"),
            "school_id": school_id(identity),
            "biz_type": biz_type,
            "biz_id": biz_id,
            "anomaly_type": anomaly_type,
            "risk_level": risk_level,
            "details_json": details,
        }
    )
    audit(identity, biz_type, biz_id, f"{biz_type}.anomaly_detected", {"anomaly_type": anomaly_type, "risk_level": risk_level})
    return created
