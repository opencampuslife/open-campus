from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "mealbot-service" / "src"))
sys.path.insert(0, str(ROOT / "services" / "api-gateway" / "src"))

from app.config import load_settings
from app.db.connection import get_conn
from app.db.repositories.worker_heartbeats import get_heartbeat, heartbeat
from health_checks import healthz, readyz, worker_status
from mealbot_gateway import post_mealbot_lock, post_mealbot_meal_order, post_vendor_confirmation
from structured_logger import structured_log


def logistics_identity() -> dict[str, str]:
    return {
        "user_id": "logistics_001",
        "role": "logistics_staff",
        "school_id": "school_demo",
        "campus": "school_demo",
    }


def parent_identity() -> dict[str, str]:
    return {
        "user_id": "parent_demo_001",
        "wecom_userid": "parent_demo_001",
        "role": "parent_or_student_h5",
        "school_id": "school_demo",
        "campus": "school_demo",
        "student_id": "student_demo_001",
    }


class Sprint6ReleaseHardeningTest(unittest.TestCase):
    def test_config_reports_required_prod_settings_without_exposing_secrets(self) -> None:
        settings = load_settings({"ENVIRONMENT": "prod", "WECOM_SECRET": "do-not-print"})
        self.assertIn("DATABASE_URL is required", settings.validation_errors())
        summary = settings.safe_summary()
        self.assertNotIn("do-not-print", json.dumps(summary))
        self.assertTrue(summary["wecom_secret_configured"])

    def test_prod_readiness_rejects_placeholder_h5_callback_origin(self) -> None:
        settings = load_settings(
            {
                "ENVIRONMENT": "prod",
                "DATABASE_URL": "postgresql://db/campus",
                "APP_BASE_URL": "https://your-domain.com",
                "WECOM_CORP_ID": "ww_demo",
                "WECOM_AGENT_ID": "1000002",
                "WECOM_SECRET": "secret",
                "WECOM_TOKEN": "token",
                "WECOM_ENCODING_AES_KEY": "aes",
            }
        )
        self.assertIn(
            "APP_BASE_URL must be an externally reachable HTTPS origin in production",
            settings.validation_errors(),
        )

    def test_structured_logs_mask_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            event = structured_log(
                Path(temp_dir), "secrets.test",
                details={"access_token": "access-value", "nested": {"encoding_aes_key": "aes-value"}},
            )
        self.assertEqual(event["details"]["access_token"], "[REDACTED]")
        self.assertEqual(event["details"]["nested"]["encoding_aes_key"], "[REDACTED]")

    def test_healthz_is_liveness_only(self) -> None:
        self.assertEqual(healthz(ROOT), {"ok": True})

    def test_readyz_fails_with_unavailable_database(self) -> None:
        with patch.dict(os.environ, {"DATABASE_URL": "postgresql://localhost:1/nope", "ENVIRONMENT": "dev"}, clear=False):
            result = readyz(ROOT)
        self.assertFalse(result["ok"])
        self.assertEqual(result["checks"]["postgres"], "unavailable")

    def test_worker_heartbeat_is_reported(self) -> None:
        heartbeat("reminder_worker", school_id="school_demo", metadata={"processed": 2})
        stored = get_heartbeat("reminder_worker")
        self.assertIsNotNone(stored["last_heartbeat_at"])
        status = worker_status(ROOT)
        self.assertIn("reminder_worker", status["workers"])

    def test_meal_lock_and_vendor_creation_are_audited(self) -> None:
        meal_date = date.today() + timedelta(days=84)
        with get_conn() as conn:
            conn.execute("DELETE FROM vendor_confirmations WHERE meal_lock_id IN (SELECT lock_id FROM meal_locks WHERE meal_date = %s)", (meal_date,))
            conn.execute("DELETE FROM meal_locks WHERE meal_date = %s", (meal_date,))
            conn.execute("DELETE FROM reminder_tasks WHERE biz_id IN (SELECT order_id FROM meal_orders WHERE meal_date = %s)", (meal_date,))
            conn.execute("DELETE FROM meal_orders WHERE meal_date = %s", (meal_date,))
        post_mealbot_meal_order({
            "student_id": "student_demo_001",
            "class_id": "class_g7_1",
            "meal_date": meal_date.isoformat(),
            "meal_type": "lunch",
            "action": "order",
        }, parent_identity(), ROOT)
        locked = post_mealbot_lock({"meal_date": meal_date.isoformat(), "meal_type": "lunch"}, logistics_identity(), ROOT)
        post_vendor_confirmation({"meal_lock_id": locked["lock"]["lock_id"]}, logistics_identity(), ROOT)
        with get_conn() as conn:
            actions = {
                row["action"] for row in conn.execute(
                    "SELECT action FROM operation_logs WHERE biz_id IN (%s, %s)",
                    (locked["lock"]["lock_id"], locked["lock"]["lock_id"]),
                ).fetchall()
            }
            vendor_logged = conn.execute(
                "SELECT count(*) AS count FROM operation_logs WHERE action = 'vendor_confirmation.created' AND after_json->>'meal_lock_id' = %s",
                (locked["lock"]["lock_id"],),
            ).fetchone()["count"]
        self.assertIn("meal_lock.created", actions)
        self.assertGreaterEqual(vendor_logged, 1)


if __name__ == "__main__":
    unittest.main()
