from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def create_handoff(
    *,
    project_root: Path,
    session_id: str,
    identity: dict[str, Any],
    message: str,
    answer: str,
    intent: str,
    retrieval: dict[str, Any],
) -> dict[str, Any]:
    summary = {
        "session_id": session_id,
        "user_id": identity.get("user_id"),
        "role": identity.get("role"),
        "campus": identity.get("campus", "all"),
        "intent": intent,
        "message": message,
        "recommended_action": _recommend_action(message, intent),
        "lead_score": _score_lead(message, intent),
        "resolved_topics": [chunk["title"] for chunk in retrieval.get("allowed_chunks", [])[:3]],
        "handoff_summary": _build_summary(message, answer, retrieval),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _append_jsonl(project_root / "data" / "crm" / "leads.jsonl", summary)
    return summary


def _build_summary(message: str, answer: str, retrieval: dict[str, Any]) -> str:
    sources = "、".join(dict.fromkeys(chunk["title"] for chunk in retrieval.get("allowed_chunks", [])[:3]))
    source_text = f"已参考资料：{sources}。" if sources else "当前未命中可引用资料。"
    return f"用户问题：{message}\n系统答复：{answer}\n{source_text}"


def _recommend_action(message: str, intent: str) -> str:
    if any(token in message for token in ["报名", "预约", "到校", "试听"]):
        return "安排顾问一对一跟进并确认到校或测评时间"
    if intent == "pricing_consulting" or any(token in message for token in ["优惠", "学费", "价格"]):
        return "安排顾问进行费用口径说明并判断是否需要分期或活动政策解读"
    return "继续收集学生分数、科类、目标和薄弱科目，补全画像后跟进"


def _score_lead(message: str, intent: str) -> int:
    score = 40
    if intent == "class_recommendation":
        score += 20
    if intent == "pricing_consulting":
        score += 10
    for token in ["报名", "预约", "到校", "试听", "电话", "微信"]:
        if token in message:
            score += 10
    return min(score, 100)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
