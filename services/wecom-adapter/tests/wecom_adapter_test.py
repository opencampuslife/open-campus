from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "services" / "wecom-adapter" / "src"
sys.path.append(str(SRC))

from wecom_adapter import WeComAdapter  # noqa: E402


class WeComAdapterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.calls: list[tuple[str, str]] = []

        def transport(method: str, endpoint: str, params, body):
            self.calls.append((method, endpoint))
            if endpoint == "/cgi-bin/gettoken":
                return {"errcode": 0, "access_token": "token-1", "expires_in": 7200}
            if endpoint == "/cgi-bin/user/getuserinfo":
                return {"errcode": 0, "UserId": "teacher_001"}
            if endpoint.endswith("/send"):
                return {"errcode": 0, "msgid": "ok"}
            if endpoint == "/cgi-bin/media/upload":
                return {"errcode": 0, "media_id": "media-1"}
            return {"errcode": 0}

        self.adapter = WeComAdapter(self.root, transport=transport)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_token_is_cached(self) -> None:
        first = self.adapter.get_access_token()
        second = self.adapter.get_access_token()
        self.assertEqual(first, "token-1")
        self.assertEqual(second, "token-1")
        self.assertEqual(self.calls.count(("GET", "/cgi-bin/gettoken")), 1)

    def test_send_app_message_writes_redacted_audit(self) -> None:
        self.adapter.send_app_message({"touser": "teacher_001", "secret_key": "raw-secret"})
        audit_path = self.root / "data" / "campus" / "wecom" / "wecom_audit.jsonl"
        audit = audit_path.read_text(encoding="utf-8").splitlines()[-1]
        record = json.loads(audit)
        self.assertEqual(record["status"], "ok")
        self.assertEqual(record["payload"]["secret_key"], "[REDACTED]")

    def test_send_app_message_masks_vendor_confirm_token_in_audit(self) -> None:
        self.adapter.send_app_message({
            "touser": "vendor_001",
            "msgtype": "text",
            "text": {"content": "请确认 /vendor/confirm?t=RAW_VENDOR_TOKEN"},
            "confirm_url": "https://school.example.com/vendor/confirm?t=RAW_VENDOR_TOKEN",
        })
        audit_path = self.root / "data" / "campus" / "wecom" / "wecom_audit.jsonl"
        audit = audit_path.read_text(encoding="utf-8").splitlines()[-1]
        record = json.loads(audit)
        self.assertIn("t=[REDACTED]", record["payload"]["confirm_url"])
        self.assertIn("t=[REDACTED]", record["payload"]["text"]["content"])
        self.assertNotIn("RAW_VENDOR_TOKEN", json.dumps(record, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
