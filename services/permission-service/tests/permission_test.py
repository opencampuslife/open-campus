from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PERMISSION_SRC = ROOT / "services" / "permission-service" / "src"
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
sys.path.extend([str(PERMISSION_SRC), str(KNOWLEDGE_SRC)])

from access_checker import can_access  # noqa: E402
from loader import load_knowledge  # noqa: E402
from scope_builder import build_scope  # noqa: E402


class PermissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        _, cls.chunks, _ = load_knowledge(ROOT / "knowledge_vault")

    def chunk(self, doc_id: str) -> dict:
        return next(c for c in self.chunks if c["doc_id"] == doc_id)

    def test_parent_cannot_access_internal_sales_script(self) -> None:
        scope = build_scope({"role": "parent", "campus": "zhengzhou"}, ROOT)
        ok, reason = can_access(self.chunk("sales_price_sensitive_2026"), scope)
        self.assertFalse(ok)
        self.assertIn(reason, {"visibility_denied", "data_level_denied", "role_denied", "forbidden_tag"})

    def test_student_cannot_access_internal_sales_strategy(self) -> None:
        scope = build_scope({"role": "student", "campus": "zhengzhou"}, ROOT)
        ok, _ = can_access(self.chunk("sales_price_sensitive_2026"), scope)
        self.assertFalse(ok)

    def test_sales_can_access_internal_sales_script(self) -> None:
        scope = build_scope({"role": "sales", "campus": "zhengzhou"}, ROOT)
        ok, reason = can_access(self.chunk("sales_price_sensitive_2026"), scope)
        self.assertTrue(ok, reason)


if __name__ == "__main__":
    unittest.main()

