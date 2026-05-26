from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.db.repositories import campus_modules as repo
from app.modules.campus.shared import actor_id, anomaly, audit, entity_id, queue_ocr, school_id


def create_batch(identity: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    batch = repo.create_score_batch(
        {
            "batch_id": entity_id("SCORE"),
            "school_id": school_id(identity),
            "class_id": str(payload["class_id"]),
            "exam_name": str(payload["exam_name"]),
            "subject": str(payload["subject"]),
            "max_score": Decimal(str(payload.get("max_score", 100))),
            "attachment_id": payload.get("attachment_id"),
            "created_by": actor_id(identity),
        }
    )
    job = queue_ocr(identity, "score_extract", batch["batch_id"], batch.get("attachment_id"), payload.get("fixture_entries"))
    audit(identity, "score_batch", batch["batch_id"], "score_batch.created", {"subject": batch["subject"]})
    return {"batch": batch, "ocr_job": job}


def apply_extraction(identity: dict[str, Any], batch_id: str, extracted_entries: list[dict[str, Any]]) -> dict[str, Any]:
    batch = repo.get_score_batch(batch_id)
    if not batch or batch["school_id"] != school_id(identity):
        raise ValueError("SCORE_BATCH_NOT_ACCESSIBLE")
    prepared: list[dict[str, Any]] = []
    seen: set[str] = set()
    findings: list[dict[str, Any]] = []
    for source in extracted_entries:
        student_no = str(source.get("student_no", "")).strip()
        student = repo.find_student_by_no(batch["school_id"], batch["class_id"], student_no) if student_no else None
        score = Decimal(str(source["score"])) if source.get("score") not in (None, "") else None
        entry = {
            "entry_id": entity_id("SE"),
            "student_id": student["student_id"] if student else None,
            "student_no": student_no or None,
            "student_name": str(source.get("student_name", "")) or (student["name"] if student else "未识别"),
            "score": score,
            "confidence": source.get("confidence"),
        }
        prepared.append(entry)
        if not student:
            findings.append({"entry": entry, "type": "student_unmatched", "message": "学生无法匹配", "risk": "high"})
        if score is None or score < 0 or score > batch["max_score"]:
            findings.append({"entry": entry, "type": "score_out_of_range", "message": "成绩超出允许范围", "risk": "high"})
        if student_no in seen:
            findings.append({"entry": entry, "type": "duplicate_student", "message": "批次中学生重复", "risk": "high"})
        seen.add(student_no)
    rows = repo.replace_score_extraction(batch_id, batch["school_id"], prepared)
    row_by_id = {row["entry_id"]: row for row in rows}
    anomalies = []
    for finding in findings:
        entry_id = finding["entry"]["entry_id"]
        item = repo.create_score_anomaly(
            {
                "anomaly_id": entity_id("SA"),
                "school_id": batch["school_id"],
                "batch_id": batch_id,
                "entry_id": row_by_id[entry_id]["entry_id"],
                "anomaly_type": finding["type"],
                "message": finding["message"],
                "risk_level": finding["risk"],
            }
        )
        anomaly(identity, "score_batch", batch_id, finding["type"], finding["risk"], {"entry_id": entry_id})
        anomalies.append(item)
    audit(identity, "score_batch", batch_id, "score_entry.ocr_extracted", {"entry_count": len(rows), "anomaly_count": len(anomalies)})
    return {"entries": rows, "anomalies": anomalies, "status": "review_required"}


def confirm_batch(identity: dict[str, Any], batch_id: str) -> dict[str, Any]:
    batch = repo.confirm_score_batch(batch_id, actor_id(identity))
    if not batch:
        raise ValueError("SCORE_BATCH_NOT_REVIEWABLE")
    audit(identity, "score_batch", batch_id, "score_batch.confirmed", {"status": "confirmed"})
    return batch


def create_rpa_dry_run(identity: dict[str, Any], batch_id: str) -> dict[str, Any]:
    batch = repo.get_score_batch(batch_id)
    if not batch or batch["school_id"] != school_id(identity) or batch["status"] != "confirmed":
        raise ValueError("SCORE_BATCH_NOT_CONFIRMED")
    entries = repo.list_score_entries(batch_id)
    job = repo.create_rpa_job(
        {
            "job_id": entity_id("RPA"),
            "school_id": batch["school_id"],
            "job_type": "score_export_dry_run",
            "biz_id": batch_id,
            "input_json": {"entry_count": len(entries), "subject": batch["subject"]},
            "output_json": {
                "mode": "dry_run",
                "rows": [{"student_no": row["student_no"], "score": str(row["score"])} for row in entries],
                "requires_manual_approval": True,
            },
        }
    )
    audit(identity, "score_batch", batch_id, "score_batch.rpa_dry_run_created", {"rpa_job_id": job["job_id"]})
    return job
