from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

COMPLIANCE_SRC = Path(__file__).resolve().parents[2] / "compliance-service" / "src"
sys.path.append(str(COMPLIANCE_SRC))

from checker import evaluate_answer, rewrite_answer  # noqa: E402


def check_answer(answer: str, scope: dict[str, Any], project_root: Path) -> dict[str, Any]:
    return evaluate_answer(answer, scope, project_root)


def safe_rewrite(answer: str, violations: list[str]) -> str:
    return rewrite_answer(answer, violations)
