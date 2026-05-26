from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_VISIBILITIES = {"public", "protected", "internal", "admin"}
VALID_DATA_LEVEL_INTS = {1, 2, 3, 4}
VALID_REVIEW_STATUSES = {"draft", "reviewed", "approved"}
VALID_ROLES = {"parent", "student", "sales", "teacher", "operator", "campus_admin", "admin"}
PROMISE_WORDS = ["保证", "承诺", "100%", "一定", "绝对"]

REQUIRED_FIELDS = [
    "title", "doc_id", "visibility", "allowed_roles", "data_level",
    "data_level_int", "campus_scope", "business_tags", "effective_date",
    "expiry_date", "owner", "review_status", "source_type", "version",
]


def validate_frontmatter(
    frontmatter: dict[str, Any],
    project_root: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in frontmatter or frontmatter[field] is None:
            errors.append("missing required field: {}".format(field))

    if errors:
        return {"valid": False, "errors": errors, "warnings": warnings}

    doc_id = frontmatter.get("doc_id", "")
    visibility = frontmatter.get("visibility", "")
    data_level_int = frontmatter.get("data_level_int")
    review_status = frontmatter.get("review_status", "")
    allowed_roles = frontmatter.get("allowed_roles", [])
    campus_scope = frontmatter.get("campus_scope", [])
    expiry_date = frontmatter.get("expiry_date", "")

    if project_root is not None:
        vault_dir = project_root / "knowledge_vault"
        if vault_dir.is_dir():
            existing = _find_doc_id_in_vault(vault_dir, doc_id)
            if existing:
                errors.append("doc_id '{}' already exists in {}".format(doc_id, existing))

    if visibility not in VALID_VISIBILITIES:
        errors.append(
            "invalid visibility '{}'; must be one of {}".format(
                visibility, sorted(VALID_VISIBILITIES)
            )
        )

    if data_level_int not in VALID_DATA_LEVEL_INTS:
        errors.append(
            "invalid data_level_int {}; must be one of {}".format(
                data_level_int, sorted(VALID_DATA_LEVEL_INTS)
            )
        )

    if review_status not in VALID_REVIEW_STATUSES:
        errors.append(
            "invalid review_status '{}'; must be one of {}".format(
                review_status, sorted(VALID_REVIEW_STATUSES)
            )
        )

    if review_status == "draft":
        errors.append("draft documents cannot be published")

    if expiry_date:
        try:
            exp = datetime.strptime(expiry_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if exp < datetime.now(timezone.utc):
                errors.append("expiry_date {} is in the past".format(expiry_date))
        except ValueError:
            errors.append("invalid expiry_date format '{}'; expected YYYY-MM-DD".format(expiry_date))

    if visibility == "public" and allowed_roles:
        content_str = " ".join(str(v) for v in frontmatter.values())
        for word in PROMISE_WORDS:
            if word in content_str:
                warnings.append("public document contains promise word: '{}'".format(word))

    if allowed_roles:
        if isinstance(allowed_roles, list):
            invalid_roles = [r for r in allowed_roles if r not in VALID_ROLES]
            if invalid_roles:
                errors.append(
                    "invalid allowed_roles: {}; valid roles are {}".format(
                        invalid_roles, sorted(VALID_ROLES)
                    )
                )
        else:
            errors.append("allowed_roles must be a list")
    else:
        errors.append("allowed_roles must be a non-empty list")

    if not isinstance(campus_scope, list) or len(campus_scope) == 0:
        errors.append("campus_scope must be a non-empty list")

    if len(errors) == 0:
        return {"valid": True, "errors": errors, "warnings": warnings}
    return {"valid": False, "errors": errors, "warnings": warnings}


def _find_doc_id_in_vault(vault_dir: Path, doc_id: str) -> str | None:
    for md_file in vault_dir.rglob("*.md"):
        content = md_file.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"^doc_id:\s*(.+)$", content, re.MULTILINE)
        if m and m.group(1).strip() == doc_id:
            return str(md_file.relative_to(vault_dir.parent))
    return None


def parse_frontmatter_from_md(content: str) -> tuple[dict[str, Any] | None, str]:
    if not content.startswith("---\n"):
        return None, content
    try:
        parts = content.split("---\n", 2)
        if len(parts) < 3:
            return None, content
        fm_raw = parts[1]
        body = parts[2].strip()
        fm = yaml_loads(fm_raw)
        if isinstance(fm, dict):
            return fm, body
        return None, content
    except Exception:
        return None, content


def yaml_loads(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, Any]] = [(-1, root)]
    pending_key: tuple[int, dict[str, Any], str] | None = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if pending_key and indent > pending_key[0]:
            _, parent, key = pending_key
            parent[key] = [] if line.startswith("- ") else {}
            stack.append((pending_key[0], parent[key]))
            pending_key = None

        while stack and indent <= stack[-1][0]:
            stack.pop()

        container = stack[-1][1]

        if line.startswith("- "):
            if not isinstance(container, list):
                raise ValueError("List item has non-list parent: {}".format(raw_line))
            item = line[2:].strip()
            if ":" in item and not item.startswith(("'", '"')):
                key, value = item.split(":", 1)
                obj: dict[str, Any] = {key.strip(): _yaml_scalar(value.strip())}
                container.append(obj)
                stack.append((indent, obj))
                if not value.strip():
                    pending_key = (indent, obj, key.strip())
            else:
                container.append(_yaml_scalar(item))
            continue

        if ":" not in line:
            raise ValueError("Unsupported YAML line: {}".format(raw_line))

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not isinstance(container, dict):
            raise ValueError("Map item has non-map parent: {}".format(raw_line))

        if value:
            container[key] = _yaml_scalar(value)
        else:
            container[key] = {}
            pending_key = (indent, container, key)
            stack.append((indent, container[key]))

    return root


def _yaml_scalar(value: str) -> Any:
    if value in {"null", "Null", "NULL", "~", ""}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value
