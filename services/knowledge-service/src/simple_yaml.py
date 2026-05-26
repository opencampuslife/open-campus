"""Small YAML reader for this zero-dependency P1 demo.

It supports the subset used by the scaffold configs and Markdown frontmatter:
maps, nested maps, lists, inline lists, quoted strings, numbers, booleans, and
null. Replace with PyYAML or ruamel.yaml before production.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


def load_file(path: Path) -> dict[str, Any]:
    return loads(path.read_text(encoding="utf-8"))


def loads(text: str) -> dict[str, Any]:
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
                raise ValueError(f"List item has non-list parent: {raw_line}")
            item = line[2:].strip()
            if ":" in item and not item.startswith(("'", '"')):
                key, value = item.split(":", 1)
                obj: dict[str, Any] = {key.strip(): _parse_scalar(value.strip())}
                container.append(obj)
                stack.append((indent, obj))
                if not value.strip():
                    pending_key = (indent, obj, key.strip())
            else:
                container.append(_parse_scalar(item))
            continue

        if ":" not in line:
            raise ValueError(f"Unsupported YAML line: {raw_line}")

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not isinstance(container, dict):
            raise ValueError(f"Map item has non-map parent: {raw_line}")

        if value:
            container[key] = _parse_scalar(value)
        else:
            container[key] = {}
            pending_key = (indent, container, key)
            stack.append((indent, container[key]))

    return root


def _parse_scalar(value: str) -> Any:
    if value == "":
        return None
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value in {"true", "True", "TRUE"}:
        return True
    if value in {"false", "False", "FALSE"}:
        return False
    if value.startswith("[") and value.endswith("]"):
        return ast.literal_eval(value)
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

