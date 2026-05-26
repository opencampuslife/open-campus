from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
PERMISSION_SRC = ROOT / "services" / "permission-service" / "src"
RAG_SRC = ROOT / "services" / "rag-service" / "src"
sys.path.extend([str(KNOWLEDGE_SRC), str(PERMISSION_SRC), str(RAG_SRC)])

from indexer import build_index  # noqa: E402
from retriever import search  # noqa: E402
from scope_builder import build_scope  # noqa: E402


class RagTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_index(ROOT)

    def test_parent_price_query_does_not_retrieve_internal_script(self) -> None:
        scope = build_scope({"role": "parent", "campus": "zhengzhou"}, ROOT)
        result = search("学费太贵了，你们最低能给多少？", scope, ROOT)
        doc_ids = {c["doc_id"] for c in result["allowed_chunks"]}
        self.assertNotIn("sales_price_sensitive_2026", doc_ids)
        self.assertIn("tuition_public_2026", doc_ids)

    def test_student_strategy_query_does_not_retrieve_internal_script(self) -> None:
        scope = build_scope({"role": "student", "campus": "zhengzhou"}, ROOT)
        result = search("你们招生老师遇到价格敏感用户怎么处理？", scope, ROOT)
        doc_ids = {c["doc_id"] for c in result["allowed_chunks"]}
        self.assertNotIn("sales_price_sensitive_2026", doc_ids)

    def test_sales_can_retrieve_internal_script(self) -> None:
        scope = build_scope({"role": "sales", "campus": "zhengzhou"}, ROOT)
        result = search("家长嫌贵，我应该怎么解释价格敏感用户？", scope, ROOT)
        doc_ids = {c["doc_id"] for c in result["allowed_chunks"]}
        self.assertIn("sales_price_sensitive_2026", doc_ids)


if __name__ == "__main__":
    unittest.main()

