from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
sys.path.extend([str(KNOWLEDGE_SRC), str(AGENT_SRC)])

from indexer import build_index  # noqa: E402
from pipeline import receive_message  # noqa: E402


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_index(ROOT)

    def test_parent_answer_does_not_leak_internal_pricing_strategy(self) -> None:
        result = receive_message(
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou", "auth_level": "phone_verified"},
            "学费太贵了，你们最低能给多少？",
            ROOT,
        )
        self.assertNotIn("内部优惠审批规则", result["answer"])
        self.assertNotIn("内部参考", result["answer"])
        doc_ids = {c["doc_id"] for c in result["retrieval"]["allowed_chunks"]}
        self.assertNotIn("sales_price_sensitive_2026", doc_ids)

    def test_sales_answer_marks_internal_reference(self) -> None:
        result = receive_message(
            {"user_id": "u_sales", "role": "sales", "campus": "zhengzhou", "auth_level": "staff"},
            "家长嫌贵，我应该怎么解释价格敏感用户？",
            ROOT,
        )
        self.assertIn("内部参考", result["answer"])
        doc_ids = {c["doc_id"] for c in result["retrieval"]["allowed_chunks"]}
        self.assertIn("sales_price_sensitive_2026", doc_ids)

    def test_compliance_rewrites_guaranteed_claim(self) -> None:
        result = receive_message(
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            "你们能保证提分 100 分并保证录取吗？",
            ROOT,
        )
        self.assertNotIn("保证提分 100 分", result["answer"])
        self.assertIn("不能承诺固定提分", result["answer"])


if __name__ == "__main__":
    unittest.main()

