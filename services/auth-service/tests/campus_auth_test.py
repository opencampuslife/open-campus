from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AUTH_SRC = ROOT / "services" / "auth-service" / "src"
WORKFLOW_SRC = ROOT / "services" / "workflow-service" / "src"
sys.path.extend([str(AUTH_SRC), str(WORKFLOW_SRC)])

from campus_auth import handle_wecom_callback, issue_wecom_state, load_wecom_session_identity  # noqa: E402
from campus_domain import ensure_demo_school_data  # noqa: E402


class _StubAdapter:
    def getuserinfo(self, code: str) -> dict[str, str]:
        return {"UserId": code.replace("code_", "")}


class CampusAuthTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        ensure_demo_school_data(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_issue_wecom_state(self) -> None:
        result = issue_wecom_state(self.root, "/h5/teacher")
        self.assertIn("state", result)
        self.assertEqual(result["redirect_path"], "/h5/teacher")

    def test_handle_wecom_callback_success(self) -> None:
        state = issue_wecom_state(self.root, "/h5/teacher")
        result = handle_wecom_callback(self.root, "code_teacher_001", state["state"], _StubAdapter())
        self.assertEqual(result["identity"]["role"], "head_teacher")
        self.assertEqual(result["identity"]["wecom_userid"], "teacher_001")

    def test_handle_wecom_callback_missing_mapping_fails(self) -> None:
        state = issue_wecom_state(self.root, "/h5/teacher")
        with self.assertRaisesRegex(ValueError, "not mapped"):
            handle_wecom_callback(self.root, "code_unknown", state["state"], _StubAdapter())

    def test_callback_accepts_db_identity_resolver_and_creates_session(self) -> None:
        state = issue_wecom_state(self.root, "/h5/meal/order")
        identity = {
            "user_id": "parent_live",
            "wecom_userid": "parent_live",
            "role": "parent_or_student_h5",
            "school_id": "school_demo",
            "campus": "school_demo",
            "student_id": "student_live",
        }
        result = handle_wecom_callback(
            self.root,
            "code_parent_live",
            state["state"],
            _StubAdapter(),
            identity_resolver=lambda userid: identity if userid == "parent_live" else None,
        )
        loaded = load_wecom_session_identity(self.root, result["session_id"])
        self.assertEqual(loaded, identity)
        self.assertEqual(result["redirect_path"], "/h5/meal/order")

    def test_expired_session_fails_closed(self) -> None:
        state = issue_wecom_state(self.root, "/h5/teacher")
        result = handle_wecom_callback(self.root, "code_teacher_001", state["state"], _StubAdapter())
        path = self.root / "data" / "campus" / "sessions" / f"{result['session_id']}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertIsNone(load_wecom_session_identity(self.root, result["session_id"]))
        self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
