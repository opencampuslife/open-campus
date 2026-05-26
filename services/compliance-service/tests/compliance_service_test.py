from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SERVICE_SRC = ROOT / "services" / "compliance-service" / "src"
sys.path.append(str(SERVICE_SRC))

from checker import evaluate_answer, rewrite_answer  # noqa: E402


class ComplianceServiceTest(unittest.TestCase):
    def test_external_answer_blocks_internal_reference(self) -> None:
        result = evaluate_answer("这是内部参考，不要外传。", {"role": "parent"}, ROOT)
        self.assertFalse(result["passed"])
        self.assertIn("internal_reference_leak", result["violations"])

    def test_sales_role_can_keep_internal_reference(self) -> None:
        result = evaluate_answer("内部参考：先解释公开价格区间。", {"role": "sales"}, ROOT)
        self.assertTrue(result["passed"])

    def test_phone_number_is_flagged(self) -> None:
        result = evaluate_answer("请联系 13812345678 继续报名。", {"role": "parent"}, ROOT)
        self.assertFalse(result["passed"])
        self.assertIn("privacy_phone_number", result["violations"])
        self.assertIn("隐私", rewrite_answer("x", result["violations"]))


if __name__ == "__main__":
    unittest.main()
