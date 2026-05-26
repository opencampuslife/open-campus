from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

KNOWLEDGE_SRC = Path(__file__).resolve().parents[2] / "knowledge-service" / "src"
sys.path.append(str(KNOWLEDGE_SRC))

from simple_yaml import load_file  # noqa: E402


def load_roles(project_root: Path) -> dict[str, Any]:
    return load_file(project_root / "configs" / "roles.yaml")["roles"]

