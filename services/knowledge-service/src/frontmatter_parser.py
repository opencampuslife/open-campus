from __future__ import annotations

from pathlib import Path
from typing import Any

from simple_yaml import loads


def parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} is missing YAML frontmatter")
    try:
        _, frontmatter, body = text.split("---\n", 2)
    except ValueError as exc:
        raise ValueError(f"{path} has malformed frontmatter") from exc
    metadata = loads(frontmatter)
    return metadata, body.strip()

