from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[3]
GATEWAY_SRC = ROOT / "services" / "llm-gateway" / "src"
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
sys.path.extend([str(GATEWAY_SRC), str(AGENT_SRC), str(KNOWLEDGE_SRC)])

from indexer import build_index  # noqa: E402
from pipeline import receive_message  # noqa: E402
from provider_deepseek import chat_completion  # noqa: E402
from schemas import EvidenceChunk, LLMRequest  # noqa: E402
from gateway import generate_admissions_answer  # noqa: E402

ENABLED = os.environ.get("DEEPSEEK_ENABLE_LLM") == "1" and bool(os.environ.get("DEEPSEEK_API_KEY"))


@unittest.skipUnless(ENABLED, "Requires DEEPSEEK_ENABLE_LLM=1 and valid DEEPSEEK_API_KEY")
class LiveLLMSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_index(ROOT)

    def test_real_provider_smoke_public_faq(self) -> None:
        os.environ["DEEPSEEK_ENABLE_LLM"] = "1"
        result = receive_message(
            {"user_id": "u_smoke", "role": "parent", "campus": "zhengzhou"},
            "学校有哪些课程类型？",
            ROOT,
        )
        answer = result["answer"]
        self.assertIsNotNone(answer)
        self.assertNotEqual(answer.strip(), "")
        self.assertNotIn("内部参考", answer)
        self.assertNotIn("内部优惠审批规则", answer)

    def test_real_provider_smoke_sales_internal(self) -> None:
        os.environ["DEEPSEEK_ENABLE_LLM"] = "1"
        result = receive_message(
            {"user_id": "u_smoke_sales", "role": "sales", "campus": "zhengzhou"},
            "价格敏感用户沟通规则有什么要点？",
            ROOT,
            entrypoint="sales_console",
        )
        self.assertIsNotNone(result["answer"])
        doc_ids = {c["doc_id"] for c in result["retrieval"]["allowed_chunks"]}
        self.assertIn("sales_price_sensitive_2026", doc_ids)

    def test_real_provider_smoke_visitor_no_internal_leak(self) -> None:
        os.environ["DEEPSEEK_ENABLE_LLM"] = "1"
        result = receive_message(
            {"user_id": "u_smoke_visitor", "role": "visitor", "campus": "zhengzhou"},
            "有哪些内部优惠策略？",
            ROOT,
        )
        answer = result["answer"]
        self.assertNotIn("内部优惠审批规则", answer)
        self.assertNotIn("优惠底价", answer)
        doc_ids = {c["doc_id"] for c in result["retrieval"]["allowed_chunks"]}
        self.assertNotIn("sales_price_sensitive_2026", doc_ids)

    def test_real_provider_error_timeout_fallback_to_rule_based(self) -> None:
        os.environ["DEEPSEEK_ENABLE_LLM"] = "1"
        os.environ["DEEPSEEK_API_KEY"] = "sk-valid-key-format"
        os.environ["DEEPSEEK_BASE_URL"] = "http://127.0.0.1:9"

        result = receive_message(
            {"user_id": "u_timeout", "role": "parent", "campus": "zhengzhou"},
            "报名全日制复读班需要什么条件？",
            ROOT,
        )
        answer = result["answer"]
        self.assertIsNotNone(answer)
        self.assertNotEqual(answer.strip(), "")
        self.assertIn("全日制", answer)

    def test_real_provider_error_invalid_key_fallback_to_rule_based(self) -> None:
        os.environ["DEEPSEEK_ENABLE_LLM"] = "1"
        os.environ["DEEPSEEK_API_KEY"] = "sk-this-key-does-not-exist"
        os.environ["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com"

        result = receive_message(
            {"user_id": "u_badkey", "role": "parent", "campus": "zhengzhou"},
            "孩子今年 430 分适合什么班？",
            ROOT,
        )
        answer = result["answer"]
        self.assertIsNotNone(answer)
        self.assertNotEqual(answer.strip(), "")
        self.assertIn("全日制", answer)


if __name__ == "__main__":
    unittest.main()
