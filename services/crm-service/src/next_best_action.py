from __future__ import annotations

from typing import Any


def determine_next_best_action(
    profile: dict[str, Any],
    profile_completeness: float,
    consultation_stage: str,
    recommendation: dict[str, Any] | None = None,
    has_contact: bool = False,
    intent_level: str = "medium",
) -> dict[str, Any]:
    action = "continue_conversation"
    description = ""
    priority = "medium"

    if profile_completeness < 0.45:
        action = "collect_profile"
        description = "继续收集学生/家长画像"
        priority = "high"
    elif consultation_stage == "PROFILE_COLLECTING":
        action = "collect_profile"
        description = "画像不足，优先补充关键信息"
        priority = "high"
    elif consultation_stage == "CLASS_RECOMMENDING":
        action = "recommend_class"
        description = "已具备基本画像，推荐班型"
        priority = "high"
    elif consultation_stage == "OBJECTION_HANDLING":
        action = "address_objection"
        description = "处理用户异议"
        priority = "high"
    elif consultation_stage == "READY_FOR_HANDOFF":
        action = "handoff_to_consultant"
        description = "用户请求转人工，触发 handoff"
        priority = "high"
    elif consultation_stage == "FOLLOWUP_PENDING":
        action = "schedule_followup"
        description = "安排销售跟进"
        priority = "medium"
    elif intent_level == "high" and has_contact:
        action = "assign_consultant"
        description = "高意向且有联系方式，分配顾问"
        priority = "high"
    elif intent_level == "high" and not has_contact:
        action = "elicit_contact"
        description = "高意向无联系方式，引导留电话"
        priority = "high"

    return {"action": action, "description": description, "priority": priority, "consultation_stage": consultation_stage}
