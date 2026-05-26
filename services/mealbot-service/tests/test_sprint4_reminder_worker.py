from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api-gateway" / "src"))

from app.db.connection import get_conn
from app.db.repositories import reminder_tasks as tasks_repo
from app.db.repositories import meal_orders as orders_repo
from app.modules.meal.orders import (
    submit_meal_order, lock_meal, generate_vendor_confirmation, confirm_vendor,
)
from app.modules.meal.vendor_reminders import create_vendor_reminders
from app.services.reminder_service import process_due_reminders
from app.services.message_adapters import NoopAdapter

CST = timezone(timedelta(hours=8))
SCHOOL_ID = "school_demo"
STUDENT_ID = "student_demo_001"
CLASS_ID = "class_g7_1"
TEST_DATE = date(2026, 6, 15)


class TestClaimDueTasks(unittest.TestCase):
    def tearDown(self):
        with get_conn() as conn:
            conn.execute("DELETE FROM operation_logs WHERE after_json ->> 'reminder_id' LIKE 'RT-test%%'")
            conn.execute("DELETE FROM reminder_tasks WHERE reminder_id LIKE 'RT-test%%'")

    def test_claims_only_pending_due(self):
        rid = f"RT-test-{uuid4().hex[:8]}"
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO reminder_tasks (reminder_id, school_id, biz_type, biz_id, receiver_type, receiver_id, channel, status, scheduled_at, idempotency_key)
                VALUES (%(rid)s, 'school_demo', 'meal_order', 'MO-000', 'logistics', 'default', 'noop', 'pending', now() - '1 hour'::interval, %(ikey)s)""",
                {"rid": rid, "ikey": f"test_{rid}"},
            )

        claimed = tasks_repo.claim_due_tasks("test_worker", limit=5)
        self.assertGreaterEqual(len(claimed), 1)
        for t in claimed:
            self.assertEqual(t["status"], "processing")
            self.assertEqual(t["locked_by"], "test_worker")

    def test_does_not_claim_future(self):
        rid = f"RT-test-{uuid4().hex[:8]}"
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO reminder_tasks (reminder_id, school_id, biz_type, biz_id, receiver_type, receiver_id, channel, status, scheduled_at, idempotency_key)
                VALUES (%(rid)s, 'school_demo', 'meal_order', 'MO-000', 'logistics', 'default', 'noop', 'pending', now() + '1 hour'::interval, %(ikey)s)""",
                {"rid": rid, "ikey": f"test_{rid}"},
            )

        claimed = tasks_repo.claim_due_tasks("test_worker", limit=5)
        future = [t for t in claimed if t["reminder_id"] == rid]
        self.assertEqual(len(future), 0)


class TestMarkSentSkippedFailed(unittest.TestCase):
    def tearDown(self):
        with get_conn() as conn:
            conn.execute("DELETE FROM operation_logs WHERE after_json ->> 'reminder_id' LIKE 'RT-test%%'")
            conn.execute("DELETE FROM reminder_tasks WHERE reminder_id LIKE 'RT-test%%'")

    def _create_task(self, status="pending", scheduled_offset="-1 hour"):
        rid = f"RT-test-{uuid4().hex[:8]}"
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO reminder_tasks (reminder_id, school_id, biz_type, biz_id, receiver_type, receiver_id, channel, status, scheduled_at, idempotency_key)
                VALUES (%(rid)s, 'school_demo', 'meal_order', 'MO-000', 'logistics', 'default', 'noop', %(status)s, now() + %(offset)s::interval, %(ikey)s)""",
                {"rid": rid, "status": status, "offset": scheduled_offset, "ikey": f"test_{rid}"},
            )
        return rid

    def test_mark_sent(self):
        rid = self._create_task("processing")
        result = tasks_repo.mark_sent(rid)
        self.assertEqual(result["status"], "sent")
        self.assertIsNotNone(result["sent_at"])

    def test_mark_skipped(self):
        rid = self._create_task("processing")
        result = tasks_repo.mark_skipped(rid, "already_confirmed")
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["last_error"], "already_confirmed")

    def test_mark_failed_or_retry(self):
        rid = self._create_task("processing")
        result = tasks_repo.mark_failed_or_retry(rid, "network error", max_retries=3)
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["retry_count"], 1)

    def test_max_retries_mark_failed(self):
        rid = self._create_task("processing")
        with get_conn() as conn:
            conn.execute("UPDATE reminder_tasks SET retry_count = 2 WHERE reminder_id = %(rid)s", {"rid": rid})
        result = tasks_repo.mark_failed_or_retry(rid, "final error", max_retries=3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["retry_count"], 3)


class TestVendorReminderCreation(unittest.TestCase):
    def setUp(self):
        self.clean_order_ids: list[str] = []
        self.clean_lock_ids: list[str] = []

    def tearDown(self):
        with get_conn() as conn:
            for oid in self.clean_order_ids:
                conn.execute("DELETE FROM meal_orders WHERE order_id = %(oid)s", {"oid": oid})
            for lid in self.clean_lock_ids:
                conn.execute("DELETE FROM vendor_confirmations WHERE meal_lock_id = %(lid)s", {"lid": lid})
                conn.execute("DELETE FROM meal_locks WHERE lock_id = %(lid)s", {"lid": lid})
            conn.execute("DELETE FROM reminder_tasks WHERE reminder_id LIKE 'RT-%%' AND biz_id LIKE 'VC-%%'")

    def test_create_vendor_reminders(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
            meal_date=TEST_DATE, meal_type="lunch", action="order",
        )
        self.clean_order_ids.append(order["order_id"])

        lock_result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        lock_id = lock_result["lock"]["lock_id"]
        self.clean_lock_ids.append(lock_id)

        confirm_id = f"VC-{uuid4().hex[:12]}"
        results = create_vendor_reminders(
            school_id=SCHOOL_ID, meal_lock_id=lock_id,
            confirmation_id=confirm_id, confirm_url="/vendor/confirm?t=TEST",
            meal_date=str(TEST_DATE), meal_type="lunch",
            net_total=415, vendor_name="测试供应商",
        )
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["template_id"], "vendor_confirmation_send")


class TestProcessDueReminders(unittest.TestCase):
    def setUp(self):
        self.clean_order_ids: list[str] = []
        self.clean_lock_ids: list[str] = []

    def tearDown(self):
        with get_conn() as conn:
            for oid in self.clean_order_ids:
                conn.execute("DELETE FROM meal_orders WHERE order_id = %(oid)s", {"oid": oid})
            for lid in self.clean_lock_ids:
                conn.execute("DELETE FROM vendor_confirmations WHERE meal_lock_id = %(lid)s", {"lid": lid})
                conn.execute("DELETE FROM meal_locks WHERE lock_id = %(lid)s", {"lid": lid})
            conn.execute("DELETE FROM reminder_tasks WHERE reminder_id LIKE 'RT-%%' AND idempotency_key LIKE 'test_proc%%'")
            conn.execute("DELETE FROM operation_logs WHERE after_json ->> 'reminder_id' LIKE 'RT-%%'")

    def test_process_due_sends_pending(self):
        rid = f"RT-{uuid4().hex[:12]}"
        with get_conn() as conn:
            conn.execute(
                """INSERT INTO reminder_tasks (reminder_id, school_id, biz_type, biz_id, receiver_type, receiver_id, channel, status, scheduled_at, idempotency_key)
                VALUES (%(rid)s, 'school_demo', 'meal_order', 'MO-test', 'logistics', 'default', 'noop', 'pending', now() - '1 hour'::interval, %(ikey)s)""",
                {"rid": rid, "ikey": f"test_proc_{rid}"},
            )

        counts = process_due_reminders("test_worker")
        self.assertGreaterEqual(counts["sent"], 1)
        with get_conn() as conn:
            audit = conn.execute(
                """
                SELECT action FROM operation_logs
                WHERE after_json ->> 'reminder_id' = %(rid)s
                ORDER BY created_at DESC LIMIT 1
                """,
                {"rid": rid},
            ).fetchone()
        self.assertEqual(audit["action"], "reminder_task.sent")


if __name__ == "__main__":
    unittest.main()
