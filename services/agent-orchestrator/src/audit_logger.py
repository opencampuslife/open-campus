from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def audit_log(project_root: Path, event: dict[str, Any]) -> None:
    log_dir = project_root / "data" / "audit_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    event = dict(event)
    event["created_at"] = datetime.now(timezone.utc).isoformat()
    with (log_dir / "audit.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")

