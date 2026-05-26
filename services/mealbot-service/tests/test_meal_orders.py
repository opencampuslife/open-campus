from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.db.connection import get_conn
from app.db.repositories import meal_orders as orders_repo
from app.db.repositories import attachments as attachments_repo
from app.modules.meal.orders import submit_meal_order, list_student_orders, cancel_meal_order
from app.storage.local import save_image_bytes

SCHOOL_ID = "school_demo"
STUDENT_ID = "student_demo_001"
CLASS_ID = "class_g7_1"


class TestMealOrderRepo(unittest.TestCase):
    def setUp(self):
        self.meal_date = date.today()
        self.order_id = f"MO-{uuid4().hex[:12]}"

    def tearDown(self):
        with get_conn() as conn:
            conn.execute("DELETE FROM meal_orders WHERE order_id = %(order_id)s", {"order_id": self.order_id})

    def test_create_order(self):
        order = orders_repo.create_or_update_order({
            "order_id": self.order_id,
            "school_id": SCHOOL_ID,
            "student_id": STUDENT_ID,
            "class_id": CLASS_ID,
            "meal_date": self.meal_date,
            "meal_type": "lunch",
            "action": "cancel",
            "reason": "test reason",
            "dietary_note": None,
            "submitted_by_wecom_userid": "test_user",
            "status": "submitted",
        })
        self.assertEqual(order["order_id"], self.order_id)
        self.assertEqual(order["status"], "submitted")
        self.assertEqual(order["reason"], "test reason")

    def test_idempotent_upsert(self):
        data = {
            "order_id": self.order_id,
            "school_id": SCHOOL_ID,
            "student_id": STUDENT_ID,
            "class_id": CLASS_ID,
            "meal_date": self.meal_date,
            "meal_type": "lunch",
            "action": "cancel",
            "reason": "first submit",
            "dietary_note": None,
            "submitted_by_wecom_userid": "test_user",
            "status": "submitted",
        }
        first = orders_repo.create_or_update_order(data)
        data["reason"] = "updated reason"
        second = orders_repo.create_or_update_order(data)

        self.assertEqual(first["order_id"], second["order_id"])
        self.assertEqual(second["reason"], "updated reason")

        count_sql = """
        SELECT count(*) as cnt FROM meal_orders
        WHERE student_id = %(student_id)s AND meal_date = %(meal_date)s
          AND meal_type = %(meal_type)s AND action = %(action)s
        """
        with get_conn() as conn:
            row = conn.execute(count_sql, data).fetchone()
        self.assertEqual(row["cnt"], 1)

    def test_update_status(self):
        orders_repo.create_or_update_order({
            "order_id": self.order_id,
            "school_id": SCHOOL_ID,
            "student_id": STUDENT_ID,
            "class_id": CLASS_ID,
            "meal_date": self.meal_date,
            "meal_type": "lunch",
            "action": "cancel",
            "status": "submitted",
        })
        updated = orders_repo.update_order_status(self.order_id, "locked")
        self.assertEqual(updated["status"], "locked")

    def test_list_and_cancel(self):
        orders_repo.create_or_update_order({
            "order_id": self.order_id,
            "school_id": SCHOOL_ID,
            "student_id": STUDENT_ID,
            "class_id": CLASS_ID,
            "meal_date": self.meal_date,
            "meal_type": "lunch",
            "action": "cancel",
            "status": "submitted",
        })
        orders = orders_repo.list_orders_for_student(STUDENT_ID, self.meal_date)
        self.assertGreaterEqual(len(orders), 1)

        cancelled = orders_repo.cancel_order(self.order_id)
        self.assertEqual(cancelled["status"], "cancelled")


class TestMealOrderModule(unittest.TestCase):
    def setUp(self):
        self.meal_date = date.today()
        self.order_id = f"MO-{uuid4().hex[:12]}"

    def tearDown(self):
        with get_conn() as conn:
            conn.execute("DELETE FROM meal_orders WHERE order_id = %(order_id)s", {"order_id": self.order_id})

    def test_submit_and_list(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=self.meal_date,
            meal_type="lunch",
            action="cancel",
            reason="feeling unwell",
            submitted_by_wecom_userid="test_user",
        )
        self.order_id = order["order_id"]
        self.assertEqual(order["status"], "submitted")
        self.assertEqual(order["reason"], "feeling unwell")

        orders = list_student_orders(STUDENT_ID, self.meal_date)
        self.assertGreaterEqual(len(orders), 1)

    def test_submit_with_photo(self):
        photo_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        attachment = save_image_bytes(
            file_bytes=photo_bytes,
            original_name="test.jpg",
            content_type="image/jpeg",
            school_id=SCHOOL_ID,
        )

        order = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=self.meal_date,
            meal_type="lunch",
            action="add",
            reason="extra meal",
            submitted_by_wecom_userid="test_user",
            attachment=attachment,
        )
        self.order_id = order["order_id"]
        self.assertEqual(order["status"], "submitted")

    def test_cancel_order(self):
        order = submit_meal_order(
            school_id=SCHOOL_ID,
            student_id=STUDENT_ID,
            class_id=CLASS_ID,
            meal_date=self.meal_date,
            meal_type="lunch",
            action="cancel",
            reason="test",
        )
        self.order_id = order["order_id"]

        cancelled = cancel_meal_order(order["order_id"])
        self.assertEqual(cancelled["status"], "cancelled")

    def test_invalid_action_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            submit_meal_order(
                school_id=SCHOOL_ID,
                student_id=STUDENT_ID,
                class_id=CLASS_ID,
                meal_date=self.meal_date,
                meal_type="lunch",
                action="delete",
            )
        self.assertIn("INVALID_ACTION", str(ctx.exception))


class TestImageStorage(unittest.TestCase):
    def test_save_valid_image(self):
        photo_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 100
        result = save_image_bytes(
            file_bytes=photo_bytes,
            original_name="test.jpg",
            content_type="image/jpeg",
            school_id=SCHOOL_ID,
        )
        self.assertIn("file_path", result)
        self.assertEqual(result["content_type"], "image/jpeg")
        self.assertEqual(result["sha256"], result["sha256"])
        self.assertEqual(len(result["sha256"]), 64)

        import os
        self.assertTrue(os.path.exists(result["file_path"]))
        os.remove(result["file_path"])

    def test_invalid_content_type(self):
        with self.assertRaises(ValueError) as ctx:
            save_image_bytes(
                file_bytes=b"data",
                original_name="test.gif",
                content_type="image/gif",
                school_id=SCHOOL_ID,
            )
        self.assertIn("INVALID_IMAGE_TYPE", str(ctx.exception))

    def test_image_too_large(self):
        with self.assertRaises(ValueError) as ctx:
            save_image_bytes(
                file_bytes=b"\xff" * (6 * 1024 * 1024),
                original_name="big.jpg",
                content_type="image/jpeg",
                school_id=SCHOOL_ID,
            )
        self.assertIn("IMAGE_TOO_LARGE", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
