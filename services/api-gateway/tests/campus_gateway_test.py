from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SRC = ROOT / "services" / "api-gateway" / "src"
WORKFLOW_SRC = ROOT / "services" / "workflow-service" / "src"
WECOM_SRC = ROOT / "services" / "wecom-adapter" / "src"
AUTH_SRC = ROOT / "services" / "auth-service" / "src"
sys.path.extend([str(SERVICE_SRC), str(WORKFLOW_SRC), str(WECOM_SRC), str(AUTH_SRC)])

from campus_gateway import (  # noqa: E402
    approve_campus_leave,
    assign_campus_repair,
    cancel_campus_meal_order,
    close_campus_repair,
    complete_campus_repair,
    confirm_campus_delivery,
    get_campus_daily_report,
    get_campus_meal_summary,
    issue_campus_wecom_state,
    list_campus_leaves,
    post_campus_leave,
    post_campus_meal_order,
    post_campus_repair,
)
from campus_domain import ensure_demo_school_data, issue_vendor_token  # noqa: E402


def _parent_identity(student_id: str = "student_demo_001") -> dict[str, str]:
    return {
        "user_id": "parent_demo_001",
        "role": "parent_or_student_h5",
        "campus": "school_demo",
        "auth_level": "phone_verified",
        "school_id": "school_demo",
        "student_id": student_id,
    }


def _teacher_identity() -> dict[str, str]:
    return {
        "user_id": "user_teacher_001",
        "role": "head_teacher",
        "campus": "school_demo",
        "auth_level": "wecom_oauth",
        "school_id": "school_demo",
        "class_ids": ["class_g7_1"],
    }


def _logistics_identity() -> dict[str, str]:
    return {
        "user_id": "user_logistics_001",
        "role": "logistics_staff",
        "campus": "school_demo",
        "auth_level": "wecom_oauth",
        "school_id": "school_demo",
    }


def _vendor_identity() -> dict[str, str]:
    return {
        "user_id": "vendor_link",
        "role": "vendor_link_user",
        "campus": "school_demo",
        "auth_level": "signed_token",
        "school_id": "school_demo",
    }


class CampusGatewayTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        ensure_demo_school_data(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_issue_wecom_state(self) -> None:
        state = issue_campus_wecom_state({"redirect_path": "/h5/teacher"}, _teacher_identity(), self.root)
        self.assertEqual(state["redirect_path"], "/h5/teacher")

    def test_leave_flow_submit_approve_and_list(self) -> None:
        with patch("campus_gateway._leave_notifier", lambda *args, **kwargs: None):
            leave = post_campus_leave(
                {
                    "student_id": "student_demo_001",
                    "type": "sick",
                    "start_time": "2026-05-25T08:00:00+08:00",
                    "end_time": "2026-05-25T18:00:00+08:00",
                    "reason": "发烧请假",
                },
                _parent_identity(),
                self.root,
            )
            self.assertEqual(leave["status"], "pending")
            approved = approve_campus_leave(leave["leave_id"], {"note": "注意休息"}, _teacher_identity(), self.root)
            self.assertEqual(approved["status"], "approved")
            listing = list_campus_leaves(_teacher_identity(), self.root)
            self.assertEqual(listing["total"], 1)

    def test_meal_flow_cancel_before_lock_and_vendor_confirm(self) -> None:
        order = post_campus_meal_order(
            {
                "student_id": "student_demo_001",
                "meal_date": "2026-05-25",
                "meal_type": "lunch",
                "action": "order",
            },
            _parent_identity(),
            self.root,
        )
        cancelled = cancel_campus_meal_order(order["order_id"], {}, _parent_identity(), self.root)
        self.assertEqual(cancelled["status"], "cancelled")

        post_campus_meal_order(
            {
                "student_id": "student_demo_001",
                "meal_date": "2026-05-25",
                "meal_type": "lunch",
                "action": "order",
                "dietary_note": "少盐",
            },
            _parent_identity(),
            self.root,
        )
        summary = get_campus_meal_summary({"date": "2026-05-25", "lock": "1"}, _logistics_identity(), self.root)
        vendor_token = issue_vendor_token(self.root, summary["delivery"]["delivery_id"])["token"]
        confirmed = confirm_campus_delivery(
            summary["delivery"]["delivery_id"],
            {"token": vendor_token, "note": "已装车"},
            _vendor_identity(),
            self.root,
        )
        self.assertEqual(confirmed["status"], "confirmed")

    def test_repair_flow_and_daily_report(self) -> None:
        ticket = post_campus_repair(
            {
                "class_id": "class_g7_1",
                "location_type": "classroom",
                "location_detail": "七年级1班",
                "description": "教室灯不亮，有漏电风险",
            },
            _teacher_identity(),
            self.root,
        )
        self.assertEqual(ticket["ai_suggestion"]["priority"], "urgent")
        assigned = assign_campus_repair(ticket["ticket_id"], {"assignee_id": "user_repair_001"}, _logistics_identity(), self.root)
        self.assertEqual(assigned["status"], "processing")
        completed = complete_campus_repair(ticket["ticket_id"], {"result_note": "已更换线路"}, _logistics_identity(), self.root)
        self.assertEqual(completed["status"], "completed")
        closed = close_campus_repair(ticket["ticket_id"], {}, _teacher_identity(), self.root)
        self.assertEqual(closed["status"], "closed")

        report = get_campus_daily_report({"date": str(closed["created_at"])[:10]}, _logistics_identity(), self.root)
        self.assertIn("summary", report)
        self.assertGreaterEqual(report["summary"]["repair"]["total"], 1)

    def test_ai_sidecar_failure_does_not_block_repair(self) -> None:
        with patch("campus_domain.suggest_repair_classification", side_effect=RuntimeError("llm unavailable")):
            ticket = post_campus_repair(
                {
                    "class_id": "class_g7_1",
                    "location_type": "classroom",
                    "description": "窗户把手坏了",
                },
                _teacher_identity(),
                self.root,
            )
        self.assertEqual(ticket["status"], "pending")
        self.assertEqual(ticket["ai_suggestion"]["source"], "fallback_sidecar")


if __name__ == "__main__":
    unittest.main()
