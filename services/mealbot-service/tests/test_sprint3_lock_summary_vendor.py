from __future__ import annotations

import sys
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api-gateway" / "src"))

from app.db.connection import get_conn
from app.db.repositories import meal_orders as orders_repo
from app.db.repositories import meal_locks as locks_repo
from app.modules.meal.orders import (
    submit_meal_order,
    cancel_meal_order,
    lock_meal,
    generate_vendor_confirmation,
    get_logistics_summary,
    confirm_vendor,
    MealLockedError,
)
from app.modules.meal.vendor import generate_raw_token, token_to_hash

SCHOOL_ID = "school_demo"
STUDENT_ID = "student_demo_001"
CLASS_ID = "class_g7_1"
TEST_DATE = date(2026, 6, 10)


class TestLockMechanism(unittest.TestCase):
    def setUp(self):
        self.clean_order_ids: list[str] = []
        self.clean_lock_ids: list[str] = []

    def tearDown(self):
        with get_conn() as conn:
            for oid in self.clean_order_ids:
                conn.execute("DELETE FROM meal_orders WHERE order_id = %(oid)s", {"oid": oid})
                conn.execute("DELETE FROM reminder_tasks WHERE biz_id = %(oid)s", {"oid": oid})
            for lid in self.clean_lock_ids:
                conn.execute("DELETE FROM vendor_confirmations WHERE meal_lock_id = %(lid)s", {"lid": lid})
                conn.execute("DELETE FROM meal_locks WHERE lock_id = %(lid)s", {"lid": lid})

    def _make_order(self, action="order", meal_type="lunch"):
        order = submit_meal_order(
            school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
            meal_date=TEST_DATE, meal_type=meal_type, action=action,
            reason="test",
        )
        self.clean_order_ids.append(order["order_id"])
        return order

    def test_lock_snapshots_summary(self):
        self._make_order("order", "lunch")
        self._make_order("cancel", "lunch")

        result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        self.clean_lock_ids.append(result["lock"]["lock_id"])
        self.assertEqual(result["locked_count"], 2)
        self.assertIn("snapshot", result)
        self.assertEqual(result["snapshot"]["net_total"], 0)

    def test_lock_is_idempotent(self):
        self._make_order("order", "lunch")
        r1 = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        self.clean_lock_ids.append(r1["lock"]["lock_id"])

        r2 = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        self.assertEqual(r2.get("message"), "already_locked")

    def test_meal_locked_rejects_submit(self):
        self._make_order("order", "lunch")
        result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        self.clean_lock_ids.append(result["lock"]["lock_id"])

        with self.assertRaises(MealLockedError) as ctx:
            submit_meal_order(
                school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
                meal_date=TEST_DATE, meal_type="lunch", action="add",
            )
        self.assertEqual(ctx.exception.code, "MEAL_LOCKED")

    def test_admin_override_allowed_after_lock(self):
        self._make_order("order", "lunch")
        result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        self.clean_lock_ids.append(result["lock"]["lock_id"])

        order = submit_meal_order(
            school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
            meal_date=TEST_DATE, meal_type="lunch", action="add",
            admin_override=True,
        )
        self.clean_order_ids.append(order["order_id"])
        self.assertEqual(order["status"], "submitted")


class TestVendorToken(unittest.TestCase):
    def test_generate_raw_token(self):
        token, h = generate_raw_token()
        self.assertGreater(len(token), 20)
        self.assertEqual(len(h), 64)

    def test_token_hash_matches(self):
        token, h1 = generate_raw_token()
        h2 = token_to_hash(token)
        self.assertEqual(h1, h2)

    def test_different_tokens_produce_different_hashes(self):
        _, h1 = generate_raw_token()
        _, h2 = generate_raw_token()
        self.assertNotEqual(h1, h2)


class TestVendorConfirmation(unittest.TestCase):
    def setUp(self):
        self.clean_order_ids: list[str] = []
        self.clean_lock_ids: list[str] = []

    def tearDown(self):
        with get_conn() as conn:
            for oid in self.clean_order_ids:
                conn.execute("DELETE FROM meal_orders WHERE order_id = %(oid)s", {"oid": oid})
                conn.execute("DELETE FROM reminder_tasks WHERE biz_id = %(oid)s", {"oid": oid})
            for lid in self.clean_lock_ids:
                conn.execute("DELETE FROM vendor_confirmations WHERE meal_lock_id = %(lid)s", {"lid": lid})
                conn.execute("DELETE FROM meal_locks WHERE lock_id = %(lid)s", {"lid": lid})

    def test_full_confirm_flow(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
            meal_date=TEST_DATE, meal_type="lunch", action="order",
        )
        self.clean_order_ids.append(order["order_id"])

        lock_result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        lock_id = lock_result["lock"]["lock_id"]
        self.clean_lock_ids.append(lock_id)

        vc = generate_vendor_confirmation(
            lock_id=lock_id, school_id=SCHOOL_ID,
            vendor_name="测试供应商", vendor_contact="13800000000",
        )
        self.assertIn("confirm_url", vc)
        token = vc["confirm_url"].split("t=")[-1]

        result = confirm_vendor(token=token, action="confirmed", confirmed_by="王师傅")
        self.assertTrue(result["ok"])
        self.assertEqual(result["confirmation"]["status"], "confirmed")

    def test_invalid_token_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            confirm_vendor(token="bad-token", action="confirmed")
        self.assertIn("INVALID_VENDOR_TOKEN", str(ctx.exception))

    def test_double_confirm_rejected(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
            meal_date=TEST_DATE, meal_type="lunch", action="order",
        )
        self.clean_order_ids.append(order["order_id"])

        lock_result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        lock_id = lock_result["lock"]["lock_id"]
        self.clean_lock_ids.append(lock_id)

        vc = generate_vendor_confirmation(
            lock_id=lock_id, school_id=SCHOOL_ID,
            vendor_name="测试供应商",
        )
        token = vc["confirm_url"].split("t=")[-1]

        confirm_vendor(token=token, action="confirmed", confirmed_by="王师傅")
        with self.assertRaises(ValueError) as ctx:
            confirm_vendor(token=token, action="confirmed")
        self.assertIn("ALREADY_CONFIRMED", str(ctx.exception))

    def test_abnormal_saves_note(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
            meal_date=TEST_DATE, meal_type="lunch", action="order",
        )
        self.clean_order_ids.append(order["order_id"])

        lock_result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        lock_id = lock_result["lock"]["lock_id"]
        self.clean_lock_ids.append(lock_id)

        vc = generate_vendor_confirmation(
            lock_id=lock_id, school_id=SCHOOL_ID, vendor_name="测试供应商",
        )
        token = vc["confirm_url"].split("t=")[-1]

        result = confirm_vendor(
            token=token, action="abnormal", confirmed_by="李师傅",
            abnormal_note="少送了5份午餐",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["confirmation"]["status"], "abnormal")
        self.assertIn("少送了5份午餐", result["confirmation"].get("abnormal_note", ""))


class TestLogisticsSummary(unittest.TestCase):
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

    def test_summary_with_locks(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID, student_id=STUDENT_ID, class_id=CLASS_ID,
            meal_date=TEST_DATE, meal_type="lunch", action="order",
        )
        self.clean_order_ids.append(order["order_id"])

        result = lock_meal(SCHOOL_ID, TEST_DATE, "lunch")
        self.clean_lock_ids.append(result["lock"]["lock_id"])

        summary = get_logistics_summary(SCHOOL_ID, TEST_DATE)
        self.assertTrue(summary["locks"])
        self.assertEqual(len(summary["locks"]), 1)
        self.assertEqual(summary["locks"][0]["meal_type"], "lunch")


if __name__ == "__main__":
    unittest.main()
