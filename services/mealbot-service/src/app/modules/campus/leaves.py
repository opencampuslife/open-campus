from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.repositories import campus_modules as repo
from app.modules.campus.shared import actor_id, audit, entity_id, schedule_reminder, school_id


def create_request(identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    leave = repo.create_leave(
        {
            "leave_id": entity_id("LEAVE"),
            "school_id": school_id(identity),
            "student_id": str(payload["student_id"]),
            "class_id": str(payload["class_id"]),
            "type": str(payload.get("type", "personal")),
            "start_time": payload["start_time"],
            "end_time": payload["end_time"],
            "reason": str(payload["reason"]),
            "submitted_by": actor_id(identity),
        }
    )
    schedule_reminder(
        identity,
        biz_type="leave_request",
        biz_id=leave["leave_id"],
        receiver_type="head_teacher",
        receiver_id=leave["class_id"],
        template_id="leave_pending_approval",
        payload={"leave_id": leave["leave_id"], "student_id": leave["student_id"]},
    )
    audit(identity, "leave_request", leave["leave_id"], "leave_request.created", {"status": "pending"})
    return leave


def decide(identity: dict[str, Any], leave_id: str, decision: str, note: str = "") -> dict[str, Any]:
    status = "approved" if decision == "approve" else "rejected"
    leave = repo.update_leave_decision(leave_id, status, actor_id(identity), note)
    if not leave:
        raise ValueError("LEAVE_NOT_PENDING")
    if status == "approved":
        end_time = leave["end_time"]
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)
        schedule_reminder(
            identity,
            biz_type="leave_return",
            biz_id=leave["leave_id"],
            receiver_type="parent",
            receiver_id=leave["student_id"],
            template_id="leave_return_due",
            payload={"leave_id": leave["leave_id"], "student_id": leave["student_id"]},
            scheduled_at=end_time if end_time.tzinfo else end_time.replace(tzinfo=timezone.utc),
        )
    audit(identity, "leave_request", leave_id, f"leave_request.{status}", {"status": status})
    return leave


def confirm_return(identity: dict[str, Any], leave_id: str) -> dict[str, Any]:
    leave = repo.mark_leave_returned(leave_id, actor_id(identity))
    if not leave:
        raise ValueError("LEAVE_CANNOT_RETURN")
    audit(identity, "leave_request", leave_id, "leave_request.returned", {"status": "returned"})
    return leave


def process_overdue_returns(identity: dict[str, Any]) -> dict[str, Any]:
    overdue = repo.mark_overdue_returns(school_id(identity))
    for leave in overdue:
        schedule_reminder(
            identity,
            biz_type="leave_return",
            biz_id=leave["leave_id"],
            receiver_type="academic_staff",
            receiver_id="default",
            template_id="leave_overdue_escalation",
            payload={"leave_id": leave["leave_id"], "student_id": leave["student_id"]},
            unique_suffix="escalation",
        )
        audit(identity, "leave_request", leave["leave_id"], "leave_request.overdue_return", {"status": "overdue_return"})
    return {"overdue": overdue, "count": len(overdue)}
