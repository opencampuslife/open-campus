from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

KNOWLEDGE_SRC = Path(__file__).resolve().parents[2] / "knowledge-service" / "src"
sys.path.append(str(KNOWLEDGE_SRC))

from simple_yaml import load_file  # noqa: E402

EXTERNAL_ROLES = {"visitor", "student", "parent"}
PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")


def evaluate_answer(answer: str, scope: dict[str, Any], project_root: Path) -> dict[str, Any]:
    rules = load_file(project_root / "configs" / "compliance_rules.yaml")
    role = scope.get("role", "visitor")
    external_role = role in EXTERNAL_ROLES
    violations: list[str] = []

    blocked_phrases = list(rules.get("blocked_phrases", []))
    if not external_role:
        blocked_phrases = [phrase for phrase in blocked_phrases if phrase not in {"优惠底价", "内部名额"}]

    violations.extend(phrase for phrase in blocked_phrases if phrase in answer)

    if external_role and any(term in answer for term in ["内部参考", "内部规则", "内部话术", "内部优惠"]):
        violations.append("internal_reference_leak")

    if PHONE_PATTERN.search(answer):
        violations.append("privacy_phone_number")

    if "100%" in answer or "一定会" in answer:
        violations.append("absolute_claim")

    guidance = _build_guidance(violations, rules)
    return {
        "passed": not violations,
        "violations": violations,
        "rewrite_guidance": guidance,
    }


def rewrite_answer(answer: str, violations: list[str]) -> str:
    if "privacy_phone_number" in violations:
        return (
            "这个问题涉及个人隐私信息，当前不能直接展示联系方式或学生识别信息。"
            "建议由顾问在授权场景下继续跟进。"
        )

    if "internal_reference_leak" in violations or "优惠底价" in violations:
        return (
            "这个问题需要按学校正式口径处理，不能透露未公开的优惠、内部规则或内部参考内容。"
            "可以先根据学生基础、目标、薄弱科目和意向校区做评估，再由顾问提供合规说明。"
        )

    return (
        "这个问题需要按学校正式口径处理，不能承诺固定提分、保证录取，"
        "也不能透露未公开的优惠或内部规则。可以先根据学生基础、目标、薄弱科目和意向校区做评估，"
        "再由顾问提供合规说明。"
    )


def _build_guidance(violations: list[str], rules: dict[str, Any]) -> list[str]:
    guidance_map = rules.get("rewrite_guidance", {})
    guidance: list[str] = []
    if any(v in violations for v in ["保证录取", "保证提分", "absolute_claim"]):
        guidance.append(str(guidance_map.get("promise_risk", "")))
    if any(v in violations for v in ["优惠底价", "internal_reference_leak"]):
        guidance.append(str(guidance_map.get("pricing_risk", "")))
    if "privacy_phone_number" in violations:
        guidance.append(str(guidance_map.get("privacy_risk", "")))
    return [item for item in guidance if item]
