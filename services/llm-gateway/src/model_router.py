from __future__ import annotations

import os
from typing import Any


def route_model(task: str, scope: dict[str, Any]) -> dict[str, str]:
    return {
        "provider": "deepseek",
        "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "task": task,
        "role": scope.get("role", "unknown"),
    }

