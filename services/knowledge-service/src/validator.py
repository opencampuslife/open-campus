from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = {
    "title",
    "doc_id",
    "visibility",
    "allowed_roles",
    "data_level",
    "data_level_int",
    "campus_scope",
    "business_tags",
    "effective_date",
    "expiry_date",
    "owner",
    "review_status",
    "source_type",
    "version",
}

DATA_LEVEL_MAP = {"L1": 1, "L2": 2, "L3": 3, "L4": 4}

VALID_VISIBILITY = {"public", "protected", "internal", "admin"}

VISIBILITY_DIR_MAP = {
    "public": "public",
    "protected": "protected",
    "internal": "internal",
    "admin": "admin",
}

FORBIDDEN_PROMISES = [
    "保证提分",
    "保证录取",
    "一定上本科",
    "一定能冲一本",
    "100%",
    "包过",
    "包录取",
    "内部名额",
    "最低价",
    "优惠底价",
    "一定能",
    "肯定能",
]


def validate_doc(metadata: dict[str, Any], source_uri: str) -> list[str]:
    errors: list[str] = []

    missing = sorted(REQUIRED_FIELDS - set(metadata))
    if missing:
        errors.append(f"missing frontmatter fields: {', '.join(missing)}")

    if metadata.get("visibility") not in VALID_VISIBILITY:
        errors.append(f"invalid visibility: {metadata.get('visibility')}")

    dl = metadata.get("data_level", "")
    if dl not in DATA_LEVEL_MAP:
        errors.append(f"invalid data_level: {dl}")

    dli = metadata.get("data_level_int")
    if not isinstance(dli, int) or dli < 1 or dli > 4:
        errors.append(f"invalid data_level_int: {dli}")
    elif dl in DATA_LEVEL_MAP and dli != DATA_LEVEL_MAP[dl]:
        errors.append(
            f"data_level_int {dli} does not match data_level {dl} (expected {DATA_LEVEL_MAP[dl]})"
        )

    for field in ("allowed_roles", "campus_scope", "business_tags"):
        if field in metadata and not isinstance(metadata[field], list):
            errors.append(f"frontmatter field {field} must be a list")

    allowed_roles = metadata.get("allowed_roles", [])
    known_roles = {"visitor", "student", "parent", "sales", "teacher", "operator", "campus_admin", "admin"}
    for role in allowed_roles:
        if role not in known_roles:
            errors.append(f"unknown role in allowed_roles: {role}")

    version = metadata.get("version")
    if version is not None and not isinstance(version, (int, float)):
        errors.append(f"version must be a number, got {type(version).__name__}")

    review = metadata.get("review_status", "")
    valid_statuses = {"draft", "pending_review", "approved", "rejected", "archived"}
    if review not in valid_statuses:
        errors.append(f"invalid review_status: {review}")

    effective = _parse_date(metadata.get("effective_date", ""))
    expiry = _parse_date(metadata.get("expiry_date", ""))
    if effective and expiry and effective > expiry:
        errors.append(f"effective_date ({effective}) is after expiry_date ({expiry})")

    return errors


def check_visibility_directory_consistency(
    metadata: dict[str, Any], source_uri: str
) -> list[str]:
    errors: list[str] = []
    visibility = metadata.get("visibility", "")
    path = Path(source_uri)
    expected_dir = VISIBILITY_DIR_MAP.get(visibility)
    if expected_dir and expected_dir not in path.parts:
        errors.append(
            f"visibility '{visibility}' requires doc under '{expected_dir}/' directory, "
            f"but found at '{source_uri}'"
        )
    return errors


def check_content_prohibited(content: str, visibility: str | None = None) -> list[str]:
    errors: list[str] = []
    if visibility and visibility in {"internal", "admin"}:
        return errors
    lines = content.splitlines()
    negation_keywords = ["不得", "禁止", "不应", "不能", "不要", "不可", "避免"]
    for phrase in FORBIDDEN_PROMISES:
        for i, line in enumerate(lines):
            if phrase in line:
                if any(kw in line for kw in negation_keywords):
                    continue
                errors.append(f"prohibited phrase '{phrase}' in body (line {i + 1})")
                break
    return errors


def check_public_content_leak(
    metadata: dict[str, Any], content: str, source_uri: str
) -> list[str]:
    errors: list[str] = []
    visibility = metadata.get("visibility", "")
    if visibility == "public":
        internal_signals = ["内部优惠", "内部话术", "底价", "优惠底价", "最低成交价", "折扣审批"]
        for signal in internal_signals:
            if signal in content:
                errors.append(
                    f"public doc '{source_uri}' contains internal-sounding content: '{signal}'"
                )
    return errors


def check_doc_id_uniqueness(doc_ids: dict[str, str]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for doc_id, source_uri in doc_ids.items():
        if doc_id in seen:
            errors.append(
                f"duplicate doc_id '{doc_id}' in '{source_uri}' "
                f"(already used by '{seen[doc_id]}')"
            )
        else:
            seen[doc_id] = source_uri
    return errors


def check_doc_not_expired(metadata: dict[str, Any], source_uri: str, today: date | None = None) -> bool:
    today = today or date.today()
    expiry = _parse_date(metadata.get("expiry_date", ""))
    if expiry and expiry < today:
        return False
    return True


def check_doc_is_retrievable(metadata: dict[str, Any]) -> bool:
    if metadata.get("review_status") not in {"approved", "pending_review"}:
        return False
    if not check_doc_not_expired(metadata, metadata.get("source_uri", "")):
        return False
    return True


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
