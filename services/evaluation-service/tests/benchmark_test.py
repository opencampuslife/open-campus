from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KNOWLEDGE_SRC = ROOT / "services" / "knowledge-service" / "src"
SERVICE_SRC = ROOT / "services" / "evaluation-service" / "src"
sys.path.extend([str(KNOWLEDGE_SRC), str(SERVICE_SRC)])

from benchmark import run_benchmark  # noqa: E402
from indexer import build_index  # noqa: E402


class BenchmarkTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        build_index(ROOT)

    def test_benchmark_generates_report(self) -> None:
        report = run_benchmark(ROOT)
        self.assertGreaterEqual(report["total"], 100)
        self.assertGreaterEqual(report["passed"], 75)


if __name__ == "__main__":
    unittest.main()
