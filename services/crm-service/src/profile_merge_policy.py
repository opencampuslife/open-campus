from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProfileFieldMeta:
    confidence: float = 0.0
    source: str = "inferred"
    evidence: str | None = None
    confirmed: bool = False
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ProfileMergeDecision:
    field: str
    old_value: Any = None
    new_value: Any = None
    action: str = "keep"
    reason: str = ""
    old_confidence: float | None = None
    new_confidence: float | None = None


CORRECTION_PATTERNS = [
    (re.compile(r"不是(\d{3})[,，]?是(\d{3})"), ["current_score"]),
    (re.compile(r"刚才说错了[,，]?是(.+?)(?:类|的)"), ["subject_type", "identity_type"]),
    (re.compile(r"不对[,，]?是(.+?)(?:类|的)"), ["subject_type", "identity_type"]),
    (re.compile(r"不是(.+?类)(?:的)?[,，]?是(.+?类)"), ["subject_type"]),
    (re.compile(r"不是(.+?)(?:的)?[,，]?是(.+?)分"), ["current_score"]),
    (re.compile(r"不去(.+?)[,，]?想去(.+?)(?:校区|的)"), ["preferred_campus"]),
    (re.compile(r"是(.+?)本(?:科|人)"), ["identity_type"]),
]


def detect_corrections(message: str) -> list[dict[str, Any]]:
    corrections: list[dict[str, Any]] = []
    for pattern, candidate_fields in CORRECTION_PATTERNS:
        m = pattern.search(message)
        if m:
            total_groups = len(m.groups())
            offset = max(0, total_groups - len(candidate_fields))
            for i, field in enumerate(candidate_fields):
                group_idx = i + 1 + offset
                if group_idx > total_groups:
                    group_idx = total_groups
                val = m.group(group_idx) if group_idx <= total_groups else None
                if val:
                    corrections.append({"field": field, "corrected_to": val.strip(), "marker": m.group(0)})
    return corrections


def apply_merge_policy(
    existing: dict[str, Any],
    patch_updates: dict[str, Any],
    patch_confidence: dict[str, float],
    existing_meta: dict[str, dict[str, Any]] | None = None,
    corrections: list[dict[str, Any]] | None = None,
    source: str = "explicit_user",
) -> tuple[dict[str, Any], list[ProfileMergeDecision], list[str]]:
    if existing_meta is None:
        existing_meta = {}
    if corrections is None:
        corrections = []

    correction_fields = {c["field"]: c for c in corrections}
    decisions: list[ProfileMergeDecision] = []
    warnings: list[str] = []
    merged = dict(existing)

    for field, new_value in patch_updates.items():
        old_value = existing.get(field)
        new_conf = patch_confidence.get(field, 0.5)
        old_meta = existing_meta.get(field, {})
        old_conf = old_meta.get("confidence", 1.0) if old_meta else 1.0
        old_confirmed = old_meta.get("confirmed", False) if old_meta else False

        if old_value is None or old_value == "" or old_value == 0:
            merged[field] = new_value
            decisions.append(ProfileMergeDecision(field=field, new_value=new_value, action="set", reason="new field"))
            continue

        if old_value == new_value:
            decisions.append(ProfileMergeDecision(field=field, old_value=old_value, new_value=new_value, action="keep", reason="same value, refresh confidence", old_confidence=old_conf, new_confidence=new_conf))
            continue

        if field in correction_fields:
            merged[field] = new_value
            decisions.append(ProfileMergeDecision(field=field, old_value=old_value, new_value=new_value, action="overwrite", reason="user correction", old_confidence=old_conf, new_confidence=new_conf))
            continue

        if new_conf < 0.7 and old_conf >= 0.7:
            decisions.append(ProfileMergeDecision(field=field, old_value=old_value, new_value=new_value, action="keep", reason=f"low confidence ({new_conf}) vs high ({old_conf})", old_confidence=old_conf, new_confidence=new_conf))
            continue

        if old_confirmed and source == "inferred":
            decisions.append(ProfileMergeDecision(field=field, old_value=old_value, new_value=new_value, action="keep", reason="existing confirmed, new inferred", old_confidence=old_conf, new_confidence=new_conf))
            continue

        if new_conf >= 0.7 and old_conf >= 0.7:
            decisions.append(ProfileMergeDecision(field=field, old_value=old_value, new_value=new_value, action="needs_confirmation", reason=f"conflict: {old_value} vs {new_value}", old_confidence=old_conf, new_confidence=new_conf))
            warnings.append(f"Field {field} conflict: existing '{old_value}' vs new '{new_value}' — needs confirmation")
            continue

        merged[field] = new_value
        decisions.append(ProfileMergeDecision(field=field, old_value=old_value, new_value=new_value, action="set", reason="default merge", old_confidence=old_conf, new_confidence=new_conf))

    return merged, decisions, warnings


def update_profile_meta(
    existing_meta: dict[str, Any],
    patch_updates: dict[str, Any],
    patch_confidence: dict[str, float],
    decisions: list[ProfileMergeDecision],
    evidence: str = "",
    source: str = "explicit_user",
) -> dict[str, Any]:
    meta = dict(existing_meta)
    for d in decisions:
        if d.action in ("set", "overwrite"):
            meta[d.field] = {
                "confidence": d.new_confidence or patch_confidence.get(d.field, 0.5),
                "source": source,
                "evidence": evidence[:200] if evidence else None,
                "confirmed": d.action == "overwrite",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        elif d.action in ("keep", "needs_confirmation"):
            if d.field not in meta:
                meta[d.field] = {
                    "confidence": d.new_confidence or 0.5,
                    "source": source,
                    "evidence": evidence[:200] if evidence else None,
                    "confirmed": False,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
    return meta


def confirm_profile_field(profile_meta: dict[str, Any], field: str, source: str = "sales") -> dict[str, Any]:
    if field in profile_meta:
        profile_meta[field]["confirmed"] = True
        profile_meta[field]["source"] = source
        profile_meta[field]["updated_at"] = datetime.now(timezone.utc).isoformat()
    return profile_meta
