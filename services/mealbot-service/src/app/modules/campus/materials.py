from __future__ import annotations

from typing import Any

from app.db.repositories import campus_modules as repo
from app.modules.campus.shared import actor_id, audit, entity_id, queue_ocr, schedule_reminder, school_id


def create_task(identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    task = repo.create_collection_task(
        {
            "task_id": entity_id("COLL"),
            "school_id": school_id(identity),
            "class_id": str(payload["class_id"]),
            "title": str(payload["title"]),
            "material_type": str(payload["material_type"]),
            "deadline_at": payload["deadline_at"],
            "created_by": actor_id(identity),
        }
    )
    audit(identity, "collection_task", task["task_id"], "collection_task.created", {"class_id": task["class_id"]})
    return task


def submit(identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    task = repo.get_collection_task(str(payload["task_id"]))
    if not task or task["school_id"] != school_id(identity):
        raise ValueError("COLLECTION_TASK_NOT_ACCESSIBLE")
    student = repo.get_student(str(payload["student_id"]))
    if not student or student["school_id"] != task["school_id"] or student["class_id"] != task["class_id"]:
        raise ValueError("STUDENT_NOT_IN_COLLECTION_CLASS")
    submission = repo.upsert_material_submission(
        {
            "submission_id": entity_id("MAT"),
            "school_id": task["school_id"],
            "task_id": task["task_id"],
            "student_id": str(payload["student_id"]),
            "attachment_id": payload.get("attachment_id"),
            "submitted_by": actor_id(identity),
        }
    )
    job = queue_ocr(
        identity,
        "material_extract",
        submission["submission_id"],
        submission.get("attachment_id"),
        payload.get("fixture_extraction"),
    )
    audit(identity, "material_submission", submission["submission_id"], "material_submission.created", {"task_id": task["task_id"]})
    return {"submission": submission, "ocr_job": job}


def apply_extraction(identity: dict[str, Any], submission_id: str, extracted: dict[str, Any]) -> dict[str, Any]:
    submission = repo.mark_material_review_required(submission_id, extracted)
    if not submission:
        raise ValueError("MATERIAL_SUBMISSION_NOT_FOUND")
    audit(identity, "material_submission", submission_id, "material_submission.ocr_extracted", {"review_required": True})
    return submission


def missing_and_remind(identity: dict[str, Any], task_id: str, send_reminders: bool = True) -> dict[str, Any]:
    task = repo.get_collection_task(task_id)
    if not task or task["school_id"] != school_id(identity):
        raise ValueError("COLLECTION_TASK_NOT_ACCESSIBLE")
    missing = repo.generate_material_missing(task_id, task["school_id"], task["class_id"])
    reminders = 0
    if send_reminders:
        for item in missing:
            schedule_reminder(
                identity,
                biz_type="material_missing",
                biz_id=item["missing_id"],
                receiver_type="parent",
                receiver_id=str(item.get("parent_userid") or item["student_id"]),
                template_id="material_missing_reminder",
                payload={"task_id": task_id, "student_id": item["student_id"], "title": task["title"]},
                unique_suffix="first",
            )
            repo.mark_material_reminded(item["missing_id"])
            reminders += 1
    audit(identity, "collection_task", task_id, "material_missing.reminded", {"missing_count": len(missing), "reminder_count": reminders})
    return {"task": task, "missing": missing, "reminders_created": reminders}
