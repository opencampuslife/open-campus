from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
API_SRC = ROOT / "services" / "api-gateway" / "src"
AUTH_SRC = ROOT / "services" / "auth-service" / "src"
WORKFLOW_SRC = ROOT / "services" / "workflow-service" / "src"
WECOM_SRC = ROOT / "services" / "wecom-adapter" / "src"
sys.path.extend([str(API_SRC), str(AUTH_SRC), str(WORKFLOW_SRC), str(WECOM_SRC)])

from campus_auth import handle_wecom_callback, issue_wecom_state  # noqa: E402
from campus_gateway import get_campus_wecom_start  # noqa: E402
from campus_domain import ensure_demo_school_data  # noqa: E402
from server import GaokaoHandler, _identity_from_campus_session_cookie  # noqa: E402


class _StubAdapter:
    def getuserinfo(self, code: str) -> dict[str, str]:
        return {"UserId": code}


class CampusSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        ensure_demo_school_data(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_oauth_cookie_restores_server_issued_consumer_identity(self) -> None:
        state = issue_wecom_state(self.root, "/h5/meal/order")
        expected = {
            "user_id": "parent_001",
            "wecom_userid": "parent_001",
            "role": "parent_or_student_h5",
            "school_id": "school_demo",
            "campus": "school_demo",
            "student_id": "student_001",
        }
        result = handle_wecom_callback(
            self.root,
            "parent_001",
            state["state"],
            _StubAdapter(),
            identity_resolver=lambda _: expected,
        )
        actual = _identity_from_campus_session_cookie(
            f"theme=green; campus_session={result['session_id']}",
            self.root,
        )
        self.assertEqual(actual["role"], "parent_or_student_h5")
        self.assertEqual(actual["student_id"], "student_001")

    def test_malformed_cookie_is_anonymous(self) -> None:
        self.assertEqual(_identity_from_campus_session_cookie("campus_session=../../secret", self.root), {})

    def test_wecom_start_builds_stateful_authorize_redirect(self) -> None:
        with patch.dict(
            os.environ,
            {"WECOM_CORP_ID": "ww_test", "APP_BASE_URL": "https://school.example.com"},
            clear=False,
        ):
            result = get_campus_wecom_start(
                {"redirect_path": "/h5/campus/material"},
                {"user_id": "anonymous", "role": "visitor", "campus": "all"},
                self.root,
            )
        self.assertIn("appid=ww_test", result["authorize_url"])
        self.assertIn("scope=snsapi_base", result["authorize_url"])
        self.assertIn("callback%3Fredirect%3D1", result["authorize_url"])

    def test_session_cookie_is_secure_off_loopback_https(self) -> None:
        handler = object.__new__(GaokaoHandler)
        handler.headers = {"Host": "school.example.com", "X-Forwarded-Proto": "https"}
        cookie = handler._campus_session_cookie("wecom_abcdefghijklmnop")
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Lax", cookie)
        self.assertIn("Secure", cookie)


if __name__ == "__main__":
    unittest.main()
