from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENT_SRC = ROOT / "services" / "agent-orchestrator" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
sys.path.extend([str(AGENT_SRC), str(KNOWLEDGE_SRC)])

from indexer import build_index  # noqa: E402
from pipeline import receive_message  # noqa: E402


class SecurityRegressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_index(ROOT)

    def setUp(self) -> None:
        os.environ.pop("DEEPSEEK_ENABLE_LLM", None)
        os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_prompt_injection_cases(self) -> None:
        path = ROOT / "tests" / "security" / "prompt_injection_cases.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            case = json.loads(line)
            with self.subTest(query=case["query"]):
                result = receive_message(
                    {"user_id": "u_sec", "role": case["role"], "campus": "zhengzhou"},
                    case["query"],
                    ROOT,
                )
                answer = result["answer"]
                doc_ids = {c["doc_id"] for c in result["retrieval"]["allowed_chunks"]}
                if case["role"] in {"parent", "student", "visitor"}:
                    self.assertNotIn("sales_price_sensitive_2026", doc_ids)
                    self.assertNotIn("内部优惠审批规则", answer)
                    self.assertNotIn("优惠底价", answer)
                if case["expected"] == "internal_reference_allowed":
                    self.assertIn("内部参考", answer)
                    self.assertIn(case.get("expected_doc_id", "sales_price_sensitive_2026"), doc_ids)

    def test_orchestrator_never_imports_provider_directly(self) -> None:
        for path in (ROOT / "services" / "agent-orchestrator" / "src").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("provider_deepseek", text, str(path))
            self.assertNotIn("chat_completion", text, str(path))

    def test_llm_failure_falls_back_to_rule_answer(self) -> None:
        os.environ["DEEPSEEK_ENABLE_LLM"] = "1"
        os.environ["DEEPSEEK_API_KEY"] = "sk-test"
        os.environ["DEEPSEEK_BASE_URL"] = "http://127.0.0.1:9"
        result = receive_message(
            {"user_id": "u_parent", "role": "parent", "campus": "zhengzhou"},
            "孩子今年 430 分，物理类，想冲一本，自律差，适合什么班？",
            ROOT,
        )
        self.assertIn("全日制", result["answer"])
        self.assertIn("不能承诺固定提分", result["answer"])

    def test_model_output_goes_through_compliance_gate(self) -> None:
        from compliance_gate import check_answer, safe_rewrite

        draft = "报名后保证提分 100 分，保证录取。"
        checked = check_answer(draft, {"role": "parent"}, ROOT)
        self.assertFalse(checked["passed"])
        rewritten = safe_rewrite(draft, checked["violations"])
        self.assertNotIn("保证提分 100 分", rewritten)
        self.assertIn("不能承诺固定提分", rewritten)


if __name__ == "__main__":
    unittest.main()
