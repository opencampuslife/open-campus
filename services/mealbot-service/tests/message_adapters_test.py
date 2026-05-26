from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "services" / "mealbot-service" / "src"))

from app.services.message_adapters import WeComAppAdapter


class MessageAdaptersTest(unittest.TestCase):
    def test_wecom_app_adapter_normalizes_text_payload(self) -> None:
        sent: list[dict[str, object]] = []

        class FakeAdapter:
            def send_app_message(self, payload: dict[str, object]) -> dict[str, object]:
                sent.append(payload)
                return {"errcode": 0, "msgid": "stub"}

        adapter = WeComAppAdapter(agent_id="1000001")
        adapter._adapter = FakeAdapter()  # type: ignore[assignment]

        result = adapter.send({
            "receiver_id": "teacher_001",
            "template_id": "wecom_image_confirm_link",
            "payload_json": {"content": "hello", "safe": 1},
        })

        self.assertTrue(result["ok"])
        self.assertEqual(sent[0]["touser"], "teacher_001")
        self.assertEqual(sent[0]["msgtype"], "text")
        self.assertEqual(sent[0]["agentid"], "1000001")
        self.assertEqual(sent[0]["text"], {"content": "hello"})
        self.assertEqual(sent[0]["safe"], 1)

    def test_wecom_app_adapter_preserves_explicit_msgtype_payload(self) -> None:
        sent: list[dict[str, object]] = []

        class FakeAdapter:
            def send_app_message(self, payload: dict[str, object]) -> dict[str, object]:
                sent.append(payload)
                return {"errcode": 0, "msgid": "stub"}

        adapter = WeComAppAdapter(agent_id="1000001")
        adapter._adapter = FakeAdapter()  # type: ignore[assignment]
        payload = {
            "touser": "teacher_001",
            "msgtype": "text",
            "agentid": "2000002",
            "text": {"content": "already formed"},
        }

        adapter.send({
            "receiver_id": "teacher_001",
            "template_id": "wecom_image_confirm_link",
            "payload_json": json.dumps(payload, ensure_ascii=False),
        })

        self.assertEqual(sent[0], payload)


if __name__ == "__main__":
    unittest.main()
