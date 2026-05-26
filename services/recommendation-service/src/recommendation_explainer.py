from __future__ import annotations

from recommendation_model import ClassRecommendation


def explain_recommendation(rec: ClassRecommendation, identity_type: str = "parent") -> str:
    if rec.recommended_class_type is None:
        return _no_recommendation_message(rec, identity_type)
    
    parts: list[str] = []
    parts.append(f"根据{'您目前' if identity_type == 'parent' else '目前'}提供的信息，建议优先了解「{rec.recommended_class_type}」。")
    
    if rec.reasons:
        parts.append("\n主要原因：")
        for r in rec.reasons[:3]:
            parts.append(f"- {r}")
    
    if rec.not_suitable_if:
        parts.append(f"\n但需要注意，如果{'孩子' if identity_type == 'parent' else '你'}有以下情况，这个班型不一定是最合适的：")
        for ns in rec.not_suitable_if:
            parts.append(f"- {ns}")
    
    if rec.missing_info and rec.next_questions:
        parts.append(f"\n为了做出更准确的判断，我还需要了解：")
        for q in rec.next_questions[:2]:
            parts.append(f"- {q}")
    
    if rec.risk_warnings:
        parts.append(f"\n温馨提示：")
        for w in rec.risk_warnings:
            parts.append(f"- {w}")
    
    return "\n".join(parts)


def _no_recommendation_message(rec: ClassRecommendation, identity_type: str) -> str:
    lines = ["目前信息还不够充分，暂时无法给出具体的班型建议。"]
    if rec.next_questions:
        lines.append("\n为了帮你判断合适的班型，我还需要了解以下信息：")
        for q in rec.next_questions[:2]:
            lines.append(f"- {q}")
    if rec.risk_warnings:
        lines.append(f"\n注意：")
        for w in rec.risk_warnings:
            lines.append(f"- {w}")
    return "\n".join(lines)
