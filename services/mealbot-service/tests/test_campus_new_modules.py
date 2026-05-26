from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "mealbot-service" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api-gateway" / "src"))

from app.db.connection import get_conn
from app.db.repositories.campus_identity import resolve_wecom_identity
from campus_modules_gateway import (
    post_attendance_records,
    post_attendance_session,
    post_collection_task,
    post_material_missing,
    post_material_submission,
    post_module_leave,
    post_module_leave_decision,
    post_module_leave_return,
    post_payment_confirm,
    post_payment_missing,
    post_payment_record,
    post_payment_task,
    post_process_ocr,
    post_score_batch,
    post_score_confirm,
    post_score_rpa_dry_run,
)
from app.modules.campus.reports import export_module_csv


class CampusNewModulesTest(unittest.TestCase):
    def setUp(self) -> None:
        suffix = uuid4().hex[:10]
        self.school = f"newmods_{suffix}"
        self.class_id = f"class_{suffix}"
        self.other_class = f"other_{suffix}"
        self.student = f"stu_a_{suffix}"
        self.second_student = f"stu_b_{suffix}"
        with get_conn() as conn:
            conn.execute("INSERT INTO schools (school_id, name) VALUES (%s, '模块测试学校')", (self.school,))
            conn.execute(
                "INSERT INTO classes (class_id, school_id, grade, name) VALUES (%s, %s, '高三', '高三一班'), (%s, %s, '高三', '高三二班')",
                (self.class_id, self.school, self.other_class, self.school),
            )
            conn.execute(
                """
                INSERT INTO students (student_id, school_id, class_id, name, student_no, parent_userid)
                VALUES (%s, %s, %s, '张一', 'A001', 'parent_a'), (%s, %s, %s, '张二', 'A002', 'parent_b')
                """,
                (self.student, self.school, self.class_id, self.second_student, self.school, self.class_id),
            )

    def tearDown(self) -> None:
        with get_conn() as conn:
            conn.execute("DELETE FROM schools WHERE school_id = %s", (self.school,))

    def teacher(self) -> dict[str, object]:
        return {
            "user_id": "teacher",
            "role": "head_teacher",
            "school_id": self.school,
            "campus": self.school,
            "class_ids": [self.class_id],
        }

    def parent(self) -> dict[str, str]:
        return {
            "user_id": "parent_a",
            "wecom_userid": "parent_a",
            "role": "parent_or_student_h5",
            "school_id": self.school,
            "campus": self.school,
            "student_id": self.student,
        }

    def academic(self) -> dict[str, str]:
        return {"user_id": "academic", "role": "academic_staff", "school_id": self.school, "campus": self.school}

    def finance(self) -> dict[str, str]:
        return {"user_id": "finance", "role": "finance", "school_id": self.school, "campus": self.school}

    def test_material_collection_missing_list_and_reminder(self) -> None:
        task = post_collection_task(
            {
                "class_id": self.class_id,
                "title": "体检表",
                "material_type": "health_form",
                "deadline_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            },
            self.teacher(),
        )["task"]
        post_material_submission({"task_id": task["task_id"], "student_id": self.student}, self.parent())
        result = post_material_missing(task["task_id"], {}, self.teacher())
        self.assertEqual([item["student_id"] for item in result["missing"]], [self.second_student])
        self.assertEqual(result["reminders_created"], 1)
        with get_conn() as conn:
            logged = conn.execute(
                "SELECT count(*) AS count FROM operation_logs WHERE school_id = %s AND action = 'material_missing.reminded'",
                (self.school,),
            ).fetchone()["count"]
        self.assertEqual(logged, 1)

    def test_leave_approval_attendance_matching_and_return(self) -> None:
        tomorrow = date.today() + timedelta(days=1)
        leave = post_module_leave(
            {
                "student_id": self.student,
                "class_id": self.class_id,
                "type": "sick",
                "start_time": f"{tomorrow.isoformat()}T08:00:00+08:00",
                "end_time": f"{tomorrow.isoformat()}T21:00:00+08:00",
                "reason": "身体不适",
            },
            self.parent(),
        )["leave"]
        approved = post_module_leave_decision(leave["leave_id"], "approve", {"note": "同意"}, self.teacher())["leave"]
        self.assertEqual(approved["status"], "approved")
        session = post_attendance_session(
            {"class_id": self.class_id, "attendance_date": tomorrow.isoformat(), "period": "evening_study"},
            self.teacher(),
        )["session"]
        records = post_attendance_records(
            session["session_id"],
            {"records": [{"student_id": self.student, "status": "absent"}]},
            self.teacher(),
        )
        self.assertEqual(records["records"][0]["status"], "leave")
        self.assertEqual(records["anomalies"], [])
        returned = post_module_leave_return(leave["leave_id"], {}, self.parent())["leave"]
        self.assertEqual(returned["status"], "returned")

    def test_evening_absence_creates_high_risk_anomaly_and_reminder(self) -> None:
        session = post_attendance_session(
            {"class_id": self.class_id, "attendance_date": date.today().isoformat(), "period": "evening_study"},
            self.teacher(),
        )["session"]
        result = post_attendance_records(
            session["session_id"],
            {"records": [{"student_id": self.second_student, "status": "absent"}]},
            self.teacher(),
        )
        self.assertEqual(result["anomalies"][0]["risk_level"], "high")
        with get_conn() as conn:
            reminders = conn.execute(
                "SELECT count(*) AS count FROM reminder_tasks WHERE school_id = %s AND biz_type = 'attendance_anomaly'",
                (self.school,),
            ).fetchone()["count"]
        self.assertEqual(reminders, 1)

    def test_score_extraction_is_review_only_before_confirmation(self) -> None:
        batch = post_score_batch(
            {
                "class_id": self.class_id,
                "exam_name": "月考",
                "subject": "数学",
                "max_score": 100,
                "fixture_entries": [
                    {"student_no": "A001", "student_name": "张一", "score": 88, "confidence": 0.98},
                    {"student_no": "A002", "student_name": "张二", "score": 128, "confidence": 0.95},
                ],
            },
            self.teacher(),
        )["batch"]
        post_process_ocr({"limit": 50}, self.academic())
        with get_conn() as conn:
            current = conn.execute("SELECT status FROM score_batches WHERE batch_id = %s", (batch["batch_id"],)).fetchone()
            anomaly_count = conn.execute("SELECT count(*) AS count FROM score_anomalies WHERE batch_id = %s", (batch["batch_id"],)).fetchone()["count"]
        self.assertEqual(current["status"], "review_required")
        self.assertEqual(anomaly_count, 1)
        confirmed = post_score_confirm(batch["batch_id"], {}, self.academic())["batch"]
        self.assertEqual(confirmed["status"], "confirmed")
        dry_run = post_score_rpa_dry_run(batch["batch_id"], {}, self.academic())["rpa_job"]
        self.assertEqual(dry_run["status"], "draft")
        self.assertTrue(dry_run["output_json"]["requires_manual_approval"])

    def test_payment_amount_anomaly_requires_finance_confirmation(self) -> None:
        task = post_payment_task(
            {
                "class_id": self.class_id,
                "title": "研学费用",
                "amount_due": "500.00",
                "deadline_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            },
            self.finance(),
        )["task"]
        record = post_payment_record(
            {
                "task_id": task["task_id"],
                "student_id": self.student,
                "fixture_extraction": {"name": "张一", "amount": "450.00", "transaction_ref": "private-ref"},
            },
            self.finance(),
        )["record"]
        post_process_ocr({"limit": 50}, self.finance())
        with get_conn() as conn:
            status = conn.execute("SELECT status FROM payment_records WHERE record_id = %s", (record["record_id"],)).fetchone()["status"]
            anomaly_count = conn.execute("SELECT count(*) AS count FROM payment_anomalies WHERE record_id = %s", (record["record_id"],)).fetchone()["count"]
        self.assertEqual(status, "review_required")
        self.assertEqual(anomaly_count, 1)
        confirmed = post_payment_confirm(record["record_id"], {}, self.finance())["record"]
        self.assertEqual(confirmed["status"], "confirmed")
        missing = post_payment_missing(task["task_id"], {}, self.finance())
        self.assertEqual([row["student_id"] for row in missing["missing"]], [self.second_student])

    def test_export_outputs_reviewed_operational_csv(self) -> None:
        session = post_attendance_session(
            {"class_id": self.class_id, "attendance_date": date.today().isoformat(), "period": "class"},
            self.teacher(),
        )["session"]
        post_attendance_records(
            session["session_id"],
            {"records": [{"student_id": self.student, "status": "present"}]},
            self.teacher(),
        )
        with tempfile.TemporaryDirectory() as temp:
            result = export_module_csv(self.academic(), "attendance", Path(temp))
            self.assertEqual(result["rows"], 1)
            self.assertTrue(Path(result["file_path"]).exists())

    def test_parent_cannot_cross_student_or_inject_ocr_result(self) -> None:
        task = post_payment_task(
            {
                "class_id": self.class_id,
                "title": "资料费",
                "amount_due": "20.00",
                "deadline_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            },
            self.finance(),
        )["task"]
        with self.assertRaisesRegex(ValueError, "STUDENT_NOT_ACCESSIBLE"):
            post_payment_record({"task_id": task["task_id"], "student_id": self.second_student}, self.parent())
        own = post_payment_record(
            {
                "task_id": task["task_id"],
                "student_id": self.student,
                "fixture_extraction": {"name": "张一", "amount": "20.00"},
            },
            self.parent(),
        )
        with get_conn() as conn:
            input_json = conn.execute("SELECT input_json FROM ocr_jobs WHERE job_id = %s", (own["ocr_job"]["job_id"],)).fetchone()["input_json"]
        self.assertEqual(input_json, {})

    def test_wecom_parent_binding_resolves_consumer_scope(self) -> None:
        identity = resolve_wecom_identity("parent_a", self.school)
        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity["role"], "parent_or_student_h5")
        self.assertEqual(identity["student_id"], self.student)
        self.assertEqual(identity["school_id"], self.school)


if __name__ == "__main__":
    unittest.main()
