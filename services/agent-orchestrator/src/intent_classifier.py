from __future__ import annotations


def classify_intent(message: str) -> dict[str, object]:
    if any(word in message for word in ["学费", "费用", "优惠", "最低", "贵", "多少钱"]):
        return {"intent": "pricing_consulting", "risk_level": "medium", "should_create_lead": True}
    if any(word in message for word in ["保证", "一定", "肯定", "录取", "提分"]):
        return {"intent": "promise_risk", "risk_level": "high", "should_create_lead": False}
    if any(word in message for word in ["班", "课程", "复读", "自律", "分数", "一本"]):
        return {"intent": "class_recommendation", "risk_level": "low", "should_create_lead": True}
    if any(word in message for word in ["报名", "流程", "入学", "测评"]):
        return {"intent": "enrollment_flow", "risk_level": "low", "should_create_lead": True}
    return {"intent": "faq", "risk_level": "low", "should_create_lead": False}

