from __future__ import annotations

import json
from datetime import date
from typing import Any

from psycopg.types.json import Jsonb

from app.db.connection import get_conn


def get_student(student_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM students WHERE student_id = %s", (student_id,)).fetchone()


def find_student_by_no(school_id: str, class_id: str, student_no: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE school_id = %s AND class_id = %s AND student_no = %s",
            (school_id, class_id, student_no),
        ).fetchone()


def create_collection_task(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO collection_tasks (
                task_id, school_id, class_id, title, material_type, deadline_at,
                status, created_by
            ) VALUES (
                %(task_id)s, %(school_id)s, %(class_id)s, %(title)s,
                %(material_type)s, %(deadline_at)s, 'open', %(created_by)s
            ) RETURNING *
            """,
            data,
        ).fetchone()


def get_collection_task(task_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM collection_tasks WHERE task_id = %s", (task_id,)).fetchone()


def upsert_material_submission(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO material_submissions (
                submission_id, school_id, task_id, student_id, attachment_id,
                status, submitted_by
            ) VALUES (
                %(submission_id)s, %(school_id)s, %(task_id)s, %(student_id)s,
                %(attachment_id)s, 'submitted', %(submitted_by)s
            )
            ON CONFLICT (task_id, student_id) DO UPDATE SET
                attachment_id = EXCLUDED.attachment_id,
                status = 'submitted',
                submitted_by = EXCLUDED.submitted_by,
                updated_at = now()
            RETURNING *
            """,
            data,
        ).fetchone()


def mark_material_review_required(submission_id: str, extracted: dict[str, Any]) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE material_submissions
            SET status = 'review_required', extracted_json = %s, updated_at = now()
            WHERE submission_id = %s RETURNING *
            """,
            (Jsonb(extracted), submission_id),
        ).fetchone()


def generate_material_missing(task_id: str, school_id: str, class_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO material_missing_items (missing_id, school_id, task_id, student_id)
            SELECT 'MISS-' || substr(md5(%s || ':' || s.student_id), 1, 12), %s, %s, s.student_id
            FROM students s
            WHERE s.school_id = %s AND s.class_id = %s
              AND NOT EXISTS (
                  SELECT 1 FROM material_submissions ms
                  WHERE ms.task_id = %s AND ms.student_id = s.student_id
                    AND ms.status IN ('submitted', 'processing', 'review_required', 'accepted')
              )
            ON CONFLICT (task_id, student_id) DO NOTHING
            """,
            (task_id, school_id, task_id, school_id, class_id, task_id),
        )
        return conn.execute(
            """
            SELECT mi.*, s.name AS student_name, s.parent_userid
            FROM material_missing_items mi
            JOIN students s ON s.student_id = mi.student_id
            WHERE mi.task_id = %s AND mi.status IN ('missing', 'reminded')
            ORDER BY s.name
            """,
            (task_id,),
        ).fetchall()


def mark_material_reminded(missing_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE material_missing_items SET status = 'reminded', reminded_at = now() WHERE missing_id = %s",
            (missing_id,),
        )


def create_leave(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO leave_requests (
                leave_id, school_id, student_id, class_id, type, start_time,
                end_time, reason, status, submitted_by
            ) VALUES (
                %(leave_id)s, %(school_id)s, %(student_id)s, %(class_id)s,
                %(type)s, %(start_time)s, %(end_time)s, %(reason)s,
                'pending', %(submitted_by)s
            ) RETURNING *
            """,
            data,
        ).fetchone()


def get_leave(leave_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM leave_requests WHERE leave_id = %s", (leave_id,)).fetchone()


def update_leave_decision(leave_id: str, decision: str, actor: str, note: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE leave_requests SET
                status = %s, approver_id = %s, approval_note = %s,
                approved_at = CASE WHEN %s = 'approved' THEN now() ELSE approved_at END,
                updated_at = now()
            WHERE leave_id = %s AND status = 'pending'
            RETURNING *
            """,
            (decision, actor, note, decision, leave_id),
        ).fetchone()


def mark_leave_returned(leave_id: str, actor: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE leave_requests SET status = 'returned', returned_at = now(),
                returned_by = %s, updated_at = now()
            WHERE leave_id = %s AND status IN ('approved', 'overdue_return')
            RETURNING *
            """,
            (actor, leave_id),
        ).fetchone()


def mark_overdue_returns(school_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE leave_requests SET status = 'overdue_return', updated_at = now()
            WHERE school_id = %s AND status = 'approved' AND end_time < now()
            RETURNING *
            """,
            (school_id,),
        ).fetchall()


def create_score_batch(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO score_batches (
                batch_id, school_id, class_id, exam_name, subject, max_score,
                attachment_id, status, created_by
            ) VALUES (
                %(batch_id)s, %(school_id)s, %(class_id)s, %(exam_name)s,
                %(subject)s, %(max_score)s, %(attachment_id)s, 'uploaded',
                %(created_by)s
            ) RETURNING *
            """,
            data,
        ).fetchone()


def get_score_batch(batch_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM score_batches WHERE batch_id = %s", (batch_id,)).fetchone()


def replace_score_extraction(batch_id: str, school_id: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with get_conn() as conn:
        conn.execute("DELETE FROM score_anomalies WHERE batch_id = %s", (batch_id,))
        conn.execute("DELETE FROM score_entries WHERE batch_id = %s", (batch_id,))
        rows: list[dict[str, Any]] = []
        for entry in entries:
            rows.append(
                conn.execute(
                    """
                    INSERT INTO score_entries (
                        entry_id, school_id, batch_id, student_id, student_no,
                        student_name, score, extraction_confidence
                    ) VALUES (
                        %(entry_id)s, %(school_id)s, %(batch_id)s, %(student_id)s,
                        %(student_no)s, %(student_name)s, %(score)s, %(confidence)s
                    ) RETURNING *
                    """,
                    {"school_id": school_id, "batch_id": batch_id, **entry},
                ).fetchone()
            )
        conn.execute("UPDATE score_batches SET status = 'review_required', updated_at = now() WHERE batch_id = %s", (batch_id,))
        return rows


def create_score_anomaly(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO score_anomalies (
                anomaly_id, school_id, batch_id, entry_id, anomaly_type, message, risk_level
            ) VALUES (
                %(anomaly_id)s, %(school_id)s, %(batch_id)s, %(entry_id)s,
                %(anomaly_type)s, %(message)s, %(risk_level)s
            ) RETURNING *
            """,
            data,
        ).fetchone()


def list_score_anomalies(batch_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM score_anomalies WHERE batch_id = %s ORDER BY created_at", (batch_id,)).fetchall()


def confirm_score_batch(batch_id: str, actor: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE score_anomalies SET status = 'resolved', resolved_by = %s, resolved_at = now() WHERE batch_id = %s AND status = 'open'",
            (actor, batch_id),
        )
        conn.execute(
            "UPDATE score_entries SET review_status = 'accepted', reviewed_by = %s, reviewed_at = now() WHERE batch_id = %s",
            (actor, batch_id),
        )
        return conn.execute(
            """
            UPDATE score_batches SET status = 'confirmed', confirmed_by = %s,
                confirmed_at = now(), updated_at = now()
            WHERE batch_id = %s AND status = 'review_required' RETURNING *
            """,
            (actor, batch_id),
        ).fetchone()


def list_score_entries(batch_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM score_entries WHERE batch_id = %s ORDER BY student_no, student_name",
            (batch_id,),
        ).fetchall()


def create_payment_task(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO payment_tasks (
                task_id, school_id, class_id, title, amount_due, deadline_at,
                account_note, status, created_by
            ) VALUES (
                %(task_id)s, %(school_id)s, %(class_id)s, %(title)s,
                %(amount_due)s, %(deadline_at)s, %(account_note)s, 'open',
                %(created_by)s
            ) RETURNING *
            """,
            data,
        ).fetchone()


def get_payment_task(task_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM payment_tasks WHERE task_id = %s", (task_id,)).fetchone()


def upsert_payment_record(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO payment_records (
                record_id, school_id, task_id, student_id, attachment_id,
                status, submitted_by
            ) VALUES (
                %(record_id)s, %(school_id)s, %(task_id)s, %(student_id)s,
                %(attachment_id)s, 'submitted', %(submitted_by)s
            )
            ON CONFLICT (task_id, student_id) DO UPDATE SET
                attachment_id = EXCLUDED.attachment_id, status = 'submitted',
                submitted_by = EXCLUDED.submitted_by, updated_at = now()
            RETURNING *
            """,
            data,
        ).fetchone()


def update_payment_extraction(record_id: str, extracted: dict[str, Any]) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE payment_records SET extracted_name = %(name)s,
                extracted_amount = %(amount)s, extracted_paid_at = %(paid_at)s,
                transaction_ref_hash = %(transaction_ref_hash)s,
                status = 'review_required', updated_at = now()
            WHERE record_id = %(record_id)s RETURNING *
            """,
            {"record_id": record_id, **extracted},
        ).fetchone()


def create_payment_anomaly(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO payment_anomalies (
                anomaly_id, school_id, task_id, record_id, anomaly_type, message, risk_level
            ) VALUES (
                %(anomaly_id)s, %(school_id)s, %(task_id)s, %(record_id)s,
                %(anomaly_type)s, %(message)s, %(risk_level)s
            ) RETURNING *
            """,
            data,
        ).fetchone()


def confirm_payment(record_id: str, actor: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE payment_anomalies SET status = 'resolved', resolved_by = %s, resolved_at = now() WHERE record_id = %s AND status = 'open'",
            (actor, record_id),
        )
        return conn.execute(
            """
            UPDATE payment_records SET status = 'confirmed', confirmed_by = %s,
                confirmed_at = now(), updated_at = now()
            WHERE record_id = %s AND status = 'review_required' RETURNING *
            """,
            (actor, record_id),
        ).fetchone()


def list_payment_missing(task_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT s.student_id, s.name AS student_name, s.parent_userid
            FROM payment_tasks pt
            JOIN students s ON s.school_id = pt.school_id AND s.class_id = pt.class_id
            WHERE pt.task_id = %s AND NOT EXISTS (
                SELECT 1 FROM payment_records pr
                WHERE pr.task_id = pt.task_id AND pr.student_id = s.student_id
                  AND pr.status IN ('submitted', 'processing', 'review_required', 'confirmed')
            )
            ORDER BY s.name
            """,
            (task_id,),
        ).fetchall()


def create_attendance_session(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO attendance_sessions (
                session_id, school_id, class_id, attendance_date, period, created_by
            ) VALUES (
                %(session_id)s, %(school_id)s, %(class_id)s, %(attendance_date)s,
                %(period)s, %(created_by)s
            )
            ON CONFLICT (school_id, class_id, attendance_date, period) DO UPDATE SET
                updated_at = now()
            RETURNING *
            """,
            data,
        ).fetchone()


def get_attendance_session(session_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM attendance_sessions WHERE session_id = %s", (session_id,)).fetchone()


def approved_leave_for_date(student_id: str, day: date) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT * FROM leave_requests WHERE student_id = %s AND status = 'approved'
              AND start_time::date <= %s AND end_time::date >= %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (student_id, day, day),
        ).fetchone()


def upsert_attendance_record(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO attendance_records (
                record_id, school_id, session_id, student_id, status, note,
                matched_leave_id, submitted_by
            ) VALUES (
                %(record_id)s, %(school_id)s, %(session_id)s, %(student_id)s,
                %(status)s, %(note)s, %(matched_leave_id)s, %(submitted_by)s
            )
            ON CONFLICT (session_id, student_id) DO UPDATE SET
                status = EXCLUDED.status, note = EXCLUDED.note,
                matched_leave_id = EXCLUDED.matched_leave_id,
                submitted_by = EXCLUDED.submitted_by, updated_at = now()
            RETURNING *
            """,
            data,
        ).fetchone()


def create_attendance_anomaly(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO attendance_anomalies (
                anomaly_id, school_id, session_id, record_id, student_id,
                anomaly_type, risk_level
            ) VALUES (
                %(anomaly_id)s, %(school_id)s, %(session_id)s, %(record_id)s,
                %(student_id)s, %(anomaly_type)s, %(risk_level)s
            )
            ON CONFLICT (session_id, student_id, anomaly_type) DO UPDATE SET
                status = 'open'
            RETURNING *
            """,
            data,
        ).fetchone()


def close_attendance_session(session_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "UPDATE attendance_sessions SET status = 'submitted', updated_at = now() WHERE session_id = %s RETURNING *",
            (session_id,),
        ).fetchone()


def list_attendance_anomalies(session_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM attendance_anomalies WHERE session_id = %s ORDER BY created_at", (session_id,)).fetchall()


def create_rpa_job(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO rpa_jobs (job_id, school_id, job_type, biz_id, input_json, output_json, status)
            VALUES (%(job_id)s, %(school_id)s, %(job_type)s, %(biz_id)s, %(input_json)s, %(output_json)s, 'draft')
            RETURNING *
            """,
            {
                **data,
                "input_json": Jsonb(data.get("input_json", {})),
                "output_json": Jsonb(data.get("output_json", {})),
            },
        ).fetchone()


def create_ocr_job(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO ocr_jobs (
                job_id, school_id, job_type, biz_id, attachment_id, input_json
            ) VALUES (
                %(job_id)s, %(school_id)s, %(job_type)s, %(biz_id)s,
                %(attachment_id)s, %(input_json)s
            ) RETURNING *
            """,
            {**data, "input_json": Jsonb(data.get("input_json", {}))},
        ).fetchone()


def claim_ocr_jobs(worker_id: str, limit: int = 20, school_id: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """
            WITH pending AS (
                SELECT job_id FROM ocr_jobs
                WHERE status = 'pending'
                  AND (CAST(%s AS TEXT) IS NULL OR school_id = CAST(%s AS TEXT))
                ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED
            )
            UPDATE ocr_jobs j SET status = 'processing', locked_by = %s, locked_at = now()
            FROM pending WHERE j.job_id = pending.job_id RETURNING j.*
            """,
            (school_id, school_id, limit, worker_id),
        ).fetchall()


def complete_ocr_job(job_id: str, output: dict[str, Any], status: str = "review_required") -> dict[str, Any] | None:
    serializable_output = json.loads(json.dumps(output, default=str, ensure_ascii=False))
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE ocr_jobs SET output_json = %s, status = %s,
                locked_by = NULL, locked_at = NULL, updated_at = now()
            WHERE job_id = %s RETURNING *
            """,
            (Jsonb(serializable_output), status, job_id),
        ).fetchone()


def fail_ocr_job(job_id: str, error: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            """
            UPDATE ocr_jobs SET status = 'failed', last_error = %s,
                locked_by = NULL, locked_at = NULL, updated_at = now()
            WHERE job_id = %s RETURNING *
            """,
            (error, job_id),
        ).fetchone()


def create_anomaly(data: dict[str, Any]) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO anomaly_records (
                anomaly_id, school_id, biz_type, biz_id, anomaly_type,
                risk_level, details_json
            ) VALUES (
                %(anomaly_id)s, %(school_id)s, %(biz_type)s, %(biz_id)s,
                %(anomaly_type)s, %(risk_level)s, %(details_json)s
            ) RETURNING *
            """,
            {**data, "details_json": Jsonb(data.get("details_json", {}))},
        ).fetchone()


def dashboard_summary(school_id: str) -> dict[str, Any]:
    with get_conn() as conn:
        return {
            "materials": conn.execute(
                """
                SELECT count(*) FILTER (WHERE status = 'open') AS open_tasks,
                       (SELECT count(*) FROM material_missing_items WHERE school_id = %s AND status IN ('missing', 'reminded')) AS missing
                FROM collection_tasks WHERE school_id = %s
                """,
                (school_id, school_id),
            ).fetchone(),
            "leaves": conn.execute(
                """
                SELECT count(*) FILTER (WHERE status = 'pending') AS pending,
                       count(*) FILTER (WHERE status = 'overdue_return') AS overdue_return
                FROM leave_requests WHERE school_id = %s
                """,
                (school_id,),
            ).fetchone(),
            "scores": conn.execute(
                "SELECT count(*) FILTER (WHERE status = 'review_required') AS review_required FROM score_batches WHERE school_id = %s",
                (school_id,),
            ).fetchone(),
            "payments": conn.execute(
                """
                SELECT count(*) FILTER (WHERE status = 'review_required') AS review_required,
                       (SELECT count(*) FROM payment_anomalies WHERE school_id = %s AND status = 'open') AS anomalies
                FROM payment_records WHERE school_id = %s
                """,
                (school_id, school_id),
            ).fetchone(),
            "attendance": conn.execute(
                "SELECT count(*) FILTER (WHERE status = 'open') AS open_anomalies FROM attendance_anomalies WHERE school_id = %s",
                (school_id,),
            ).fetchone(),
            "automation": conn.execute(
                "SELECT count(*) FILTER (WHERE status IN ('pending', 'processing')) AS pending_jobs FROM ocr_jobs WHERE school_id = %s",
                (school_id,),
            ).fetchone(),
        }
