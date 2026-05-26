from __future__ import annotations

from typing import Any

from app.db.repositories import campus_modules as repo
from app.modules.campus import materials, payments, scores
from app.modules.campus.shared import audit


def _system_identity(school_id: str) -> dict[str, str]:
    return {"user_id": "campus_ocr_worker", "role": "school_admin", "school_id": school_id, "campus": school_id}


def process_ocr_jobs(worker_id: str, limit: int = 20, school_id: str | None = None) -> dict[str, int]:
    counts = {"processed": 0, "review_required": 0, "failed": 0}
    for job in repo.claim_ocr_jobs(worker_id, limit, school_id):
        identity = _system_identity(str(job["school_id"]))
        try:
            fixture = (job.get("input_json") or {}).get("fixture_result")
            if fixture is None:
                output: dict[str, Any] = {
                    "review_required": True,
                    "reason": "No automatic extractor configured; provide a reviewed extraction payload.",
                }
            elif job["job_type"] == "material_extract":
                output = materials.apply_extraction(identity, str(job["biz_id"]), dict(fixture))
            elif job["job_type"] == "score_extract":
                output = scores.apply_extraction(identity, str(job["biz_id"]), list(fixture))
            elif job["job_type"] == "payment_extract":
                output = payments.apply_extraction(identity, str(job["biz_id"]), dict(fixture))
            else:
                raise ValueError("UNKNOWN_OCR_JOB_TYPE")
            repo.complete_ocr_job(job["job_id"], output, "review_required")
            audit(identity, "ocr_job", job["job_id"], "ocr_job.review_required", {"job_type": job["job_type"]})
            counts["review_required"] += 1
        except Exception as exc:
            repo.fail_ocr_job(job["job_id"], str(exc))
            audit(identity, "ocr_job", job["job_id"], "ocr_job.failed", {"job_type": job["job_type"]})
            counts["failed"] += 1
        counts["processed"] += 1
    return counts
