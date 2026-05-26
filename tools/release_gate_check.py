from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _is_true(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def evaluate_gate(name: str, report: dict[str, object], threshold: float, blocking: bool) -> tuple[str, float]:
    if "score" in report:
        score = float(report["score"])
    else:
        total = int(report.get("total", 0))
        passed = int(report.get("passed", 0))
        score = 0.0 if total == 0 else passed * 100.0 / total
    if score >= threshold:
        return "PASS", score
    return ("FAIL" if blocking else "WARN_NON_BLOCKING"), score


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--blocking", default=os.environ.get("BENCHMARK_BLOCKING", "true"))
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    blocking = _is_true(args.blocking)
    result, score = evaluate_gate(args.name, report, args.threshold, blocking)
    mode = "blocking" if blocking else "non-blocking"
    print(f"Benchmark: {args.name}")
    print(f"Score: {score:.0f}/100")
    print(f"Threshold: {args.threshold:.0f}")
    print(f"Mode: {mode}")
    print(f"Result: {result}")
    return 1 if result == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
