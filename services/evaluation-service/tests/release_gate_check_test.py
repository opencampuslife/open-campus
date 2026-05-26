from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from release_gate_check import evaluate_gate


class ReleaseGateCheckTest(unittest.TestCase):
    def test_blocking_benchmark_below_threshold_fails(self) -> None:
        result, score = evaluate_gate("mealbot_e2e", {"passed": 89, "total": 100}, 90, True)
        self.assertEqual(score, 89)
        self.assertEqual(result, "FAIL")

    def test_non_blocking_benchmark_below_threshold_warns(self) -> None:
        result, score = evaluate_gate("admissions_quality", {"passed": 79, "total": 100}, 85, False)
        self.assertEqual(score, 79)
        self.assertEqual(result, "WARN_NON_BLOCKING")

    def test_benchmark_at_threshold_passes(self) -> None:
        result, _ = evaluate_gate("mealbot_e2e", {"score": 90}, 90, True)
        self.assertEqual(result, "PASS")


if __name__ == "__main__":
    unittest.main()
