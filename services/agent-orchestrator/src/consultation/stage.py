from __future__ import annotations

from enum import Enum
from typing import Any


class ConsultationStage(str, Enum):
    PROFILE_COLLECTING = "PROFILE_COLLECTING"
    NEEDS_ASSESSMENT = "NEEDS_ASSESSMENT"
    CLASS_RECOMMENDING = "CLASS_RECOMMENDING"
    PLAN_EXPLAINING = "PLAN_EXPLAINING"
    OBJECTION_HANDLING = "OBJECTION_HANDLING"
    READY_FOR_HANDOFF = "READY_FOR_HANDOFF"
    FOLLOWUP_PENDING = "FOLLOWUP_PENDING"
    CLOSED = "CLOSED"


def determine_stage(
    profile: dict[str, Any],
    profile_completeness: float,
    message: str,
    intent: str = "",
    fsm_state: str = "CONSULTING",
    session_has_handoff: bool = False,
) -> ConsultationStage:
    if fsm_state in ("CLOSED", "FOLLOWUP_PENDING"):
        return ConsultationStage.FOLLOWUP_PENDING if session_has_handoff else ConsultationStage.CLOSED

    if session_has_handoff:
        return ConsultationStage.FOLLOWUP_PENDING

    if profile_completeness < 0.45:
        return ConsultationStage.PROFILE_COLLECTING

    required = profile.get("current_score") and profile.get("subject_type") and profile.get("target_school_level")
    if not required:
        return ConsultationStage.PROFILE_COLLECTING

    handoff_keywords = ["转人工", "打电话", "联系我", "微信", "电话", "老师", "顾问", "到校", "参观", "测评"]
    if any(kw in message for kw in handoff_keywords):
        return ConsultationStage.READY_FOR_HANDOFF

    objection_keywords = ["太贵", "不值", "效果不好", "能不能保证", "真的有用吗", "靠谱吗", "还不如"]
    if any(kw in message for kw in objection_keywords):
        return ConsultationStage.OBJECTION_HANDLING

    class_keywords = ["什么班", "哪个班", "班型", "适合什么", "推荐", "全日制", "冲刺", "小班", "封闭"]
    if any(kw in message for kw in class_keywords):
        return ConsultationStage.CLASS_RECOMMENDING

    followup_keywords = ["为什么", "有什么不同", "怎么上", "多久", "怎么样", "说说"]
    if any(kw in message for kw in followup_keywords):
        return ConsultationStage.PLAN_EXPLAINING

    if profile_completeness >= 0.45:
        return ConsultationStage.NEEDS_ASSESSMENT

    return ConsultationStage.PROFILE_COLLECTING
