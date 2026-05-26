from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from policy_loader import load_roles


DEFAULT_FORBIDDEN_TAGS = {
    "visitor": ["internal_pricing", "sales_script", "crm_rule"],
    "student": ["internal_pricing", "sales_script", "crm_rule"],
    "parent": ["internal_pricing", "sales_script", "crm_rule"],
}


def build_scope(identity: dict[str, Any], project_root: Path) -> dict[str, Any]:
    roles = load_roles(project_root)
    role = identity["role"]
    if role not in roles:
        raise ValueError(f"Unknown role: {role}")
    policy = roles[role]
    return {
        "user_id": identity.get("user_id"),
        "role": role,
        "campus": identity.get("campus", "all"),
        "auth_level": identity.get("auth_level", "anonymous"),
        "allowed_visibility": policy.get("allowed_visibility", []),
        "allowed_data_levels": policy.get("allowed_data_levels", []),
        "allowed_roles": _allowed_roles_for(role),
        "forbidden_tags": policy.get("forbidden_tags", DEFAULT_FORBIDDEN_TAGS.get(role, [])),
    }


def _allowed_roles_for(role: str) -> list[str]:
    if role in {"visitor", "student", "parent", "customer"}:
        return ["visitor", "student", "parent", "customer"]
    if role == "sales":
        return ["visitor", "student", "parent", "sales"]
    return [role]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--identity", required=True, help="JSON identity")
    args = parser.parse_args()
    print(json.dumps(build_scope(json.loads(args.identity), args.root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

