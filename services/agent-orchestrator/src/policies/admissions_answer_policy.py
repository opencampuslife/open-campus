from __future__ import annotations

from typing import Any


def build_admissions_answer(
    message: str,
    intent: str,
    profile: dict[str, Any],
    profile_completeness: float,
    consultation_stage: str,
    recommendation: dict[str, Any] | None,
    allowed_evidence: list[dict[str, Any]],
    identity_type: str = "parent",
) -> str:
    if profile_completeness < 0.45:
        return _answer_profile_collecting(profile)

    if consultation_stage == "PROFILE_COLLECTING":
        return _answer_profile_collecting(profile)

    if consultation_stage == "OBJECTION_HANDLING":
        return _answer_objection_handling(message, allowed_evidence)

    if consultation_stage == "READY_FOR_HANDOFF":
        return _answer_ready_for_handoff()

    if recommendation and recommendation.get("recommended_class_type"):
        return _answer_class_recommendation(recommendation, identity_type, allowed_evidence)

    return _answer_general(message, profile, allowed_evidence, identity_type)


def _answer_profile_collecting(profile: dict[str, Any]) -> str:
    missing = []
    if not profile.get("subject_type"):
        missing.append("孩子是物理类还是历史类？")
    if not profile.get("current_score"):
        missing.append("目前大概分数是多少？")
    if not profile.get("target_school_level"):
        missing.append("希望考上的学校层次？")

    if not missing:
        return "好的，你的基本情况我已经了解了。接下来你想了解什么方面的信息？"

    lines = ["为了给你更准确的建议，我还需要确认几个信息："]
    for i, q in enumerate(missing[:2], 1):
        lines.append(f"{i}. {q}")
    return "\n".join(lines)


def _answer_class_recommendation(
    rec: dict[str, Any],
    identity_type: str,
    allowed_evidence: list[dict[str, Any]],
) -> str:
    ct = rec.get("recommended_class_type", "")
    reasons = rec.get("reasons", [])
    not_suitable = rec.get("not_suitable_if", [])
    next_q = rec.get("next_questions", [])
    warnings = rec.get("risk_warnings", [])

    lines = [f"根据{'您' if identity_type == 'parent' else '你'}目前提供的信息，建议优先了解「{ct}」。"]
    if reasons:
        lines.append("\n主要原因：")
        for r in reasons[:3]:
            lines.append(f"- {r}")
    if not_suitable:
        lines.append(f"\n但如果{'孩子' if identity_type == 'parent' else '你'}有以下情况，这个班型未必是最优选择：")
        for ns in not_suitable:
            lines.append(f"- {ns}")
    if next_q:
        lines.append("\n下一步建议先确认：")
        for q in next_q[:2]:
            lines.append(f"- {q}")
    if warnings:
        lines.append("\n温馨提示：")
        for w in warnings:
            lines.append(f"- {w}")
    lines.append("\n下一步建议：预约学情评估，由顾问结合薄弱科目和目标进一步确认班型。")
    lines.append("说明：不能承诺固定提分或录取结果，最终效果取决于学生基础与学习执行情况。")
    source_titles = list(dict.fromkeys(str(e.get("title", "")).strip() for e in allowed_evidence if e.get("title")))
    if source_titles:
        lines.append(f"\n来源：{'、'.join(source_titles[:3])}")
    return "\n".join(lines)


def _answer_objection_handling(message: str, evidence: list[dict[str, Any]]) -> str:
    ev_titles = [e.get("title", "") for e in evidence[:2]]
    lines = ["这个顾虑是合理的。"]
    if ev_titles:
        lines.append("关于这个问题，我能基于现有资料说明一些情况。")
    lines.append("但具体是否适合您孩子的情况，建议结合测评或让顾问进一步确认。")
    return "\n".join(lines)


def _answer_ready_for_handoff() -> str:
    return "好的。我会把您的基本情况和关注点记录下来，稍后会有招生顾问联系您进一步沟通。"


def _answer_general(message: str, profile: dict[str, Any], evidence: list[dict[str, Any]], identity_type: str) -> str:
    if evidence:
        titles = [e.get("title", "") for e in evidence[:3]]
        lines = [f"根据资料{'，' + '、'.join(titles) if titles else ''}，"]
        lines.append("你可以继续咨询相关问题。如需更详细的方案，建议预约顾问进一步沟通。")
        return "\n".join(lines)
    return "你可以继续咨询相关问题。如需更详细的方案，建议预约顾问进一步沟通。"
