from __future__ import annotations

from datetime import date
from typing import Any


def can_access(item: dict[str, Any], scope: dict[str, Any], today: date | None = None) -> tuple[bool, str]:
    today = today or date.today()
    if item.get("review_status") != "approved":
        return False, "not_approved"
    if item.get("visibility") not in scope.get("allowed_visibility", []):
        return False, "visibility_denied"
    if item.get("data_level") not in scope.get("allowed_data_levels", []):
        return False, "data_level_denied"
    if scope.get("role") not in item.get("allowed_roles", []):
        return False, "role_denied"
    campuses = item.get("campus_scope", [])
    if "all" not in campuses and scope.get("campus") not in campuses:
        return False, "campus_denied"
    tags = set(item.get("business_tags", []))
    forbidden = set(scope.get("forbidden_tags", []))
    if tags & forbidden:
        return False, "forbidden_tag"
    if str(item.get("effective_date", "0000-01-01")) > today.isoformat():
        return False, "not_effective"
    if str(item.get("expiry_date", "9999-12-31")) < today.isoformat():
        return False, "expired"
    return True, "allowed"

