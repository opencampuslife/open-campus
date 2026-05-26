from __future__ import annotations

from pathlib import Path
from typing import Any


class PilotConfigError(ValueError):
    pass


def _scalar(raw: str) -> str:
    value = raw.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def load_pilot_yaml(path: Path) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current = ""
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if raw == stripped and stripped.endswith(":"):
            current = stripped[:-1]
            sections[current] = {}
            continue
        if not current or ":" not in stripped:
            raise PilotConfigError(f"INVALID_YAML_LINE:{lineno}")
        key, value = stripped.split(":", 1)
        sections[current][key.strip()] = _scalar(value)

    required = {
        "school": ("name", "timezone"),
        "wecom": ("corp_id", "agent_id", "callback_url"),
        "meal": ("lunch_cutoff", "dinner_cutoff", "extra_cutoff", "lunch_delivery_time", "dinner_delivery_time"),
        "vendor": ("name", "contact", "channel"),
    }
    missing = [
        f"{section}.{key}"
        for section, keys in required.items()
        for key in keys
        if not sections.get(section, {}).get(key)
    ]
    if missing:
        raise PilotConfigError("MISSING_CONFIG:" + ",".join(missing))
    return sections
