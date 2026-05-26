from __future__ import annotations

from datetime import date
from typing import Any

from app.db.repositories import campus_modules as repo
from app.modules.campus.shared import actor_id, anomaly, audit, entity_id, schedule_reminder, school_id


def create_session(identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    session = repo.create_attendance_session(
        {
            "session_id": entity_id("ATT"),
            "school_id": school_id(identity),
            "class_id": str(payload["class_id"]),
            "attendance_date": date.fromisoformat(str(payload["attendance_date"])),
            "period": str(payload["period"]),
            "created_by": actor_id(identity),
        }
    )
    audit(identity, "attendance_session", session["session_id"], "attendance_session.created", {"period": session["period"]})
    return session


def submit_records(identity: dict[str, Any], session_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    session = repo.get_attendance_session(session_id)
    if not session or session["school_id"] != school_id(identity):
        raise ValueError("ATTENDANCE_SESSION_NOT_ACCESSIBLE")
    saved = []
    anomalies = []
    for source in records:
        student_id = str(source["student_id"])
        record_status = str(source["status"])
        leave = repo.approved_leave_for_date(student_id, session["attendance_date"])
        matched_leave_id = leave["leave_id"] if leave and record_status in {"leave", "absent"} else None
        record = repo.upsert_attendance_record(
            {
                "record_id": entity_id("AR"),
                "school_id": session["school_id"],
                "session_id": session_id,
                "student_id": student_id,
                "status": "leave" if matched_leave_id and record_status == "absent" else record_status,
                "note": str(source.get("note", "")),
                "matched_leave_id": matched_leave_id,
                "submitted_by": actor_id(identity),
            }
        )
        saved.append(record)
        reason = ""
        risk = "medium"
        if record_status == "absent" and not matched_leave_id:
            reason = "absence_without_leave"
            risk = "high" if session["period"] == "evening_study" else "medium"
        elif record_status in {"late", "early_leave"}:
            reason = record_status
        if reason:
            found = repo.create_attendance_anomaly(
                {
                    "anomaly_id": entity_id("AA"),
                    "school_id": session["school_id"],
                    "session_id": session_id,
                    "record_id": record["record_id"],
                    "student_id": student_id,
                    "anomaly_type": reason,
                    "risk_level": risk,
                }
            )
            anomalies.append(found)
            anomaly(identity, "attendance_session", session_id, reason, risk, {"student_id": student_id})
            schedule_reminder(
                identity,
                biz_type="attendance_anomaly",
                biz_id=found["anomaly_id"],
                receiver_type="head_teacher",
                receiver_id=session["class_id"],
                template_id="attendance_anomaly_notice",
                payload={"student_id": student_id, "period": session["period"], "anomaly_type": reason},
            )
    updated = repo.close_attendance_session(session_id)
    audit(identity, "attendance_session", session_id, "attendance_record.submitted", {"record_count": len(saved), "anomaly_count": len(anomalies)})
    return {"session": updated, "records": saved, "anomalies": anomalies}
