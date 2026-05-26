from __future__ import annotations

import io
import sys
import unittest
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api-gateway" / "src"))

from app.db.connection import get_conn
from app.db.repositories import students as students_repo
from app.db.repositories import meal_orders as orders_repo
from app.db.repositories import reminder_tasks as tasks_repo
from app.modules.meal.orders import submit_meal_order
from app.modules.meal.cutoff_policy import check_meal_cutoff, CutoffError, get_cutoff_time
from app.modules.meal.reminder import create_meal_notification
from app.storage.local import save_image_bytes

CST = timezone(timedelta(hours=8))
SCHOOL_ID = "school_demo"
STUDENT_ID = "student_demo_001"
CLASS_ID = "class_g7_1"
PARENT_ID = "parent_demo_001"


class TestH5StudentsAPI(unittest.TestCase):
    def test_get_students_by_parent_with_class(self):
        rows = students_repo.get_students_by_parent_with_class(PARENT_ID, SCHOOL_ID)
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual(rows[0]["student_id"], STUDENT_ID)
        self.assertIn("class_name", rows[0])

    def test_no_students_for_unknown_parent(self):
        rows = students_repo.get_students_by_parent_with_class("nonexistent", SCHOOL_ID)
        self.assertEqual(len(rows), 0)


class TestCutoffPolicy(unittest.TestCase):
    def test_lunch_cutoff_before_930(self):
        morning = datetime(2026, 5, 26, 8, 0, tzinfo=CST)
        check_meal_cutoff("lunch", date(2026, 5, 26), now=morning)

    def test_lunch_cutoff_after_930(self):
        noon = datetime(2026, 5, 26, 10, 0, tzinfo=CST)
        with self.assertRaises(CutoffError) as ctx:
            check_meal_cutoff("lunch", date(2026, 5, 26), now=noon)
        self.assertEqual(ctx.exception.code, "MEAL_CUTOFF_EXPIRED")

    def test_past_date_always_expired(self):
        now = datetime(2026, 5, 26, 8, 0, tzinfo=CST)
        with self.assertRaises(CutoffError):
            check_meal_cutoff("lunch", date(2026, 5, 25), now=now)

    def test_future_date_always_allowed(self):
        now = datetime(2026, 5, 25, 20, 0, tzinfo=CST)
        check_meal_cutoff("lunch", date(2026, 5, 26), now=now)

    def test_dinner_cutoff_1530(self):
        late = datetime(2026, 5, 26, 16, 0, tzinfo=CST)
        with self.assertRaises(CutoffError):
            check_meal_cutoff("dinner", date(2026, 5, 26), now=late)

    def test_get_cutoff_time(self):
        self.assertEqual(get_cutoff_time("lunch"), "09:30")
        self.assertEqual(get_cutoff_time("dinner"), "15:30")

    def test_invalid_meal_type(self):
        with self.assertRaises(ValueError):
            check_meal_cutoff("breakfast", date(2026, 5, 26))


class TestReminderTaskCreation(unittest.TestCase):
    def setUp(self):
        self.order_id = f"MO-{uuid4().hex[:12]}"

    def tearDown(self):
        with get_conn() as conn:
            conn.execute("DELETE FROM reminder_tasks WHERE biz_id = %(biz_id)s", {"biz_id": self.order_id})
            conn.execute("DELETE FROM meal_orders WHERE order_id = %(order_id)s", {"order_id": self.order_id})

    def test_create_meal_notification(self):
        task = create_meal_notification(
            school_id=SCHOOL_ID,
            order_id=self.order_id,
            student_id=STUDENT_ID,
            meal_date="2026-05-26",
            meal_type="lunch",
            action="cancel",
        )
        self.assertIsNotNone(task)
        self.assertEqual(task["biz_type"], "meal_order")
        self.assertEqual(task["biz_id"], self.order_id)

    def test_notification_after_submit(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=date(2026, 5, 27),
            meal_type="lunch",
            action="order",
        )
        self.order_id = order["order_id"]

        task = create_meal_notification(
            school_id=SCHOOL_ID,
            order_id=order["order_id"],
            student_id=STUDENT_ID,
            meal_date="2026-05-27",
            meal_type="lunch",
            action="order",
        )
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "pending")


class TestMultipartSubmit(unittest.TestCase):
    def setUp(self):
        self.order_id = None

    def tearDown(self):
        if self.order_id:
            with get_conn() as conn:
                conn.execute("DELETE FROM reminder_tasks WHERE biz_id = %(biz_id)s", {"biz_id": self.order_id})
                conn.execute("DELETE FROM meal_orders WHERE order_id = %(order_id)s", {"order_id": self.order_id})

    def test_submit_with_photo_bytes(self):
        photo_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        attachment = save_image_bytes(
            file_bytes=photo_bytes,
            original_name="meal_photo.jpg",
            content_type="image/jpeg",
            school_id=SCHOOL_ID,
        )

        order = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=date(2026, 5, 27),
            meal_type="dinner",
            action="add",
            reason="extra portion",
            submitted_by_wecom_userid=PARENT_ID,
            attachment=attachment,
        )
        self.order_id = order["order_id"]
        self.assertEqual(order["status"], "submitted")
        self.assertEqual(order["submitted_by_wecom_userid"], PARENT_ID)

    def test_idempotent_multipart_submit(self):
        order1 = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=date(2026, 5, 28),
            meal_type="lunch",
            action="order",
        )
        self.order_id = order1["order_id"]

        order2 = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=date(2026, 5, 28),
            meal_type="lunch",
            action="order",
            reason="updated",
        )
        self.assertEqual(order1["order_id"], order2["order_id"])
        self.assertEqual(order2["reason"], "updated")

    def test_submit_without_photo(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=date(2026, 5, 28),
            meal_type="dinner",
            action="cancel",
            reason="going home",
        )
        self.order_id = order["order_id"]
        self.assertEqual(order["status"], "submitted")

    def test_submit_rejects_invalid_student(self):
        with self.assertRaises(ValueError) as ctx:
            submit_meal_order(
                school_id=SCHOOL_ID,
                student_id="nonexistent",
                class_id=CLASS_ID,
                meal_date=date(2026, 5, 28),
                meal_type="lunch",
                action="order",
            )
        self.assertIn("STUDENT_NOT_FOUND", str(ctx.exception))


class TestMultipartParser(unittest.TestCase):
    def test_parse_simple_multipart(self):
        boundary = "----TestBoundary"
        body = (
            f"------TestBoundary\r\n"
            f'Content-Disposition: form-data; name="student_id"\r\n'
            f"\r\n"
            f"{STUDENT_ID}\r\n"
            f"------TestBoundary\r\n"
            f'Content-Disposition: form-data; name="meal_date"\r\n'
            f"\r\n"
            f"2026-05-26\r\n"
            f"------TestBoundary\r\n"
            f'Content-Disposition: form-data; name="action"\r\n'
            f"\r\n"
            f"cancel\r\n"
            f"------TestBoundary--\r\n"
        ).encode("utf-8")

        from multipart_parser import parse_multipart
        result = parse_multipart(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual(result["student_id"], STUDENT_ID)
        self.assertEqual(result["meal_date"], "2026-05-26")
        self.assertEqual(result["action"], "cancel")

    def test_parse_multipart_with_photo(self):
        boundary = "----PhotoBound"
        body = (
            f"------PhotoBound\r\n"
            f'Content-Disposition: form-data; name="student_id"\r\n'
            f"\r\n"
            f"{STUDENT_ID}\r\n"
            f"------PhotoBound\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="test.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n"
            f"\r\n"
            f"\xff\xd8\xff\xe0"
            f"------PhotoBound--\r\n"
        ).encode("utf-8")

        from multipart_parser import parse_multipart
        result = parse_multipart(f"multipart/form-data; boundary={boundary}", body)
        self.assertEqual(result["student_id"], STUDENT_ID)
        self.assertIn("photo_bytes", result)
        self.assertGreater(len(result["photo_bytes"]), 2)


if __name__ == "__main__":
    unittest.main()
