from __future__ import annotations

import os
import sys
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
API_SRC = ROOT / "services" / "api-gateway" / "src"
MEALBOT_SRC = ROOT / "services" / "mealbot-service" / "src"
sys.path.extend([str(API_SRC), str(MEALBOT_SRC)])

from mealbot_gateway import (  # noqa: E402
    get_h5_students,
    get_logistics_meal_summary,
    get_mealbot_orders,
    post_mealbot_lock,
    post_mealbot_meal_order,
    post_mealbot_meal_order_cancel,
    post_scheduler_run_due_reminders,
    post_vendor_confirmation,
)
from app.modules.meal.orders import generate_vendor_confirmation  # noqa: E402


def _parent() -> dict[str, str]:
    return {
        "user_id": "parent_a",
        "wecom_userid": "parent_a",
        "role": "parent_or_student_h5",
        "school_id": "school_a",
        "campus": "school_a",
    }


def _logistics() -> dict[str, str]:
    return {
        "user_id": "logistics_a",
        "role": "logistics_staff",
        "school_id": "school_a",
        "campus": "school_a",
    }


class MealbotGatewayAuthorizationTest(unittest.TestCase):
    def test_h5_student_query_uses_authenticated_wecom_identity(self) -> None:
        with patch.dict(os.environ, {"GAOKAO_ENV": "production"}, clear=False), patch(
            "app.db.repositories.students.get_students_by_parent_with_class",
            return_value=[],
        ) as get_students:
            get_h5_students({"wecom_userid": "parent_b"}, _parent(), ROOT)
        get_students.assert_called_once_with("parent_a", "school_a")

    def test_parent_cannot_list_another_students_orders(self) -> None:
        with patch(
            "app.db.repositories.students.get_students_by_parent_with_class",
            return_value=[{"student_id": "student_a"}],
        ), patch("app.modules.meal.orders.list_student_orders") as list_orders:
            with self.assertRaisesRegex(ValueError, "STUDENT_NOT_ACCESSIBLE"):
                get_mealbot_orders({"student_id": "student_b"}, _parent(), ROOT)
        list_orders.assert_not_called()

    def test_parent_cannot_submit_for_another_student(self) -> None:
        with patch(
            "app.db.repositories.students.get_students_by_parent_with_class",
            return_value=[{"student_id": "student_a"}],
        ):
            with self.assertRaisesRegex(ValueError, "STUDENT_NOT_ACCESSIBLE"):
                post_mealbot_meal_order(
                    {"student_id": "student_b", "meal_date": "2026-06-30"},
                    _parent(),
                    ROOT,
                )

    def test_parent_cannot_cancel_another_students_order(self) -> None:
        order = {"order_id": "MO-1", "school_id": "school_a", "student_id": "student_b"}
        with patch("app.db.repositories.meal_orders.get_order", return_value=order), patch(
            "app.db.repositories.students.get_students_by_parent_with_class",
            return_value=[{"student_id": "student_a"}],
        ), patch("app.modules.meal.orders.cancel_meal_order") as cancel_order:
            with self.assertRaisesRegex(ValueError, "STUDENT_NOT_ACCESSIBLE"):
                post_mealbot_meal_order_cancel("MO-1", {}, _parent(), ROOT)
        cancel_order.assert_not_called()

    def test_parent_cannot_execute_operations_actions(self) -> None:
        actions = [
            lambda: post_mealbot_lock({"meal_date": "2026-06-30"}, _parent(), ROOT),
            lambda: get_logistics_meal_summary({"meal_date": "2026-06-30"}, _parent(), ROOT),
            lambda: post_vendor_confirmation({"meal_lock_id": "ML-1"}, _parent(), ROOT),
            lambda: post_scheduler_run_due_reminders({}, _parent(), ROOT),
        ]
        for action in actions:
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError, "FORBIDDEN"):
                    action()

    def test_logistics_can_read_own_school_summary(self) -> None:
        with patch(
            "app.modules.meal.orders.get_logistics_summary",
            return_value={"school_id": "school_a", "meal_date": date(2026, 6, 30), "locks": []},
        ):
            result = get_logistics_meal_summary({"meal_date": "2026-06-30"}, _logistics(), ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["school_id"], "school_a")


class MealbotDomainSchoolIsolationTest(unittest.TestCase):
    def test_confirmation_cannot_be_generated_for_another_schools_lock(self) -> None:
        with patch(
            "app.modules.meal.orders._get_lock_by_id",
            return_value={"lock_id": "ML-b", "school_id": "school_b"},
        ), patch("app.modules.meal.orders.vendor_repo.create_vendor_confirmation") as create:
            with self.assertRaisesRegex(ValueError, "LOCK_NOT_IN_SCHOOL"):
                generate_vendor_confirmation("ML-b", "school_a")
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
