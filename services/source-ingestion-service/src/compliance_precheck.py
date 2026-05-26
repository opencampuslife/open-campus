from __future__ import annotations

import re
from typing import Any

PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")
ID_CARD_PATTERN = re.compile(r"\d{17}[\dXx]")
COMPETITIVE_CLAIMS = ["最好", "第一", "唯一", "首家", "顶级", "最优秀", "no.1", "number one"]
PROMISE_LANGUAGE = ["保证提分", "承诺录取", "保证录取", "包过", "包上", "100%通过"]


def compliance_precheck(
    frontmatter: dict[str, Any],
    content: str,
) -> dict[str, Any]:
    issues: list[str] = []
    visibility = frontmatter.get("visibility", "")
    data_level_int = frontmatter.get("data_level_int", 0)

    if visibility == "public":
        if PHONE_PATTERN.search(content):
            issues.append({
                "type": "pii_phone",
                "severity": "high",
                "message": "Public document contains phone number pattern",
            })
        if ID_CARD_PATTERN.search(content):
            issues.append({
                "type": "pii_id_card",
                "severity": "high",
                "message": "Public document contains ID card number pattern",
            })
        for claim in COMPETITIVE_CLAIMS:
            if claim in content:
                issues.append({
                    "type": "competitive_claim",
                    "severity": "medium",
                    "message": "Public document contains competitive claim: '{}'".format(claim),
                })
        for phrase in PROMISE_LANGUAGE:
            if phrase in content:
                issues.append({
                    "type": "promise_language",
                    "severity": "high",
                    "message": "Public document contains promise language: '{}'".format(phrase),
                })

    if data_level_int == 1 and visibility != "public":
        issues.append({
            "type": "data_level_mismatch",
            "severity": "medium",
            "message": "data_level_int is 1 (public) but visibility is '{}'".format(visibility),
        })

    if data_level_int >= 3:
        _check_internal_scope_issues(frontmatter, content, issues)

    risk_level = _determine_risk_level(issues)
    passed = len([i for i in issues if i["severity"] == "high"]) == 0

    return {
        "passed": passed,
        "issues": issues,
        "risk_level": risk_level,
    }


def _check_internal_scope_issues(
    frontmatter: dict[str, Any],
    content: str,
    issues: list[dict[str, Any]],
) -> None:
    allowed_roles = frontmatter.get("allowed_roles", [])
    external_roles = {"parent", "student"}
    if external_roles.intersection(allowed_roles):
        issues.append({
            "type": "internal_role_leak",
            "severity": "medium",
            "message": "data_level_int >= 3 but allowed_roles includes external roles",
        })


def _determine_risk_level(issues: list[dict[str, Any]]) -> str:
    severities = [i["severity"] for i in issues]
    if "high" in severities:
        return "high"
    if "medium" in severities:
        return "medium"
    return "low"
