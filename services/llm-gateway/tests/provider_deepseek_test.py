from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = ROOT / "services" / "llm-gateway" / "src"
sys.path.append(str(GATEWAY_SRC))

from provider_deepseek import chat_completion  # noqa: E402


class ProviderDeepSeekTest(unittest.TestCase):
    def test_deepseek_v4_flash_openai_compatible_payload(self) -> None:
        captured = {}

        def fake_transport(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return json.dumps(
                {"choices": [{"message": {"content": "ok"}}]},
                ensure_ascii=False,
            ).encode("utf-8")

        result = chat_completion(
            [{"role": "user", "content": "Hello"}],
            api_key="test-key",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            transport=fake_transport,
        )

        self.assertEqual(result, "ok")
        self.assertEqual(captured["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(captured["body"]["model"], "deepseek-v4-flash")
        self.assertEqual(captured["body"]["messages"][0]["content"], "Hello")
        self.assertFalse(captured["body"]["stream"])
        self.assertEqual(captured["headers"]["Authorization"], "Bearer test-key")


if __name__ == "__main__":
    unittest.main()

