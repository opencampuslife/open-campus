from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(os.environ.get("MEALBOT_SRC", Path(__file__).resolve().parents[2])))


def run_loop() -> None:
    from app.config import load_settings
    from app.db.repositories.worker_heartbeats import heartbeat
    from app.modules.wecom.media_download import process_pending_media_downloads

    running = True

    def _shutdown(_sig: int, _frame: object) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)
    project_root = Path(os.environ.get("PROJECT_ROOT", Path(__file__).resolve().parents[6]))
    settings = load_settings()
    while running:
        counts = process_pending_media_downloads(project_root)
        heartbeat("wecom_media_worker", school_id=os.environ.get("WECOM_SCHOOL_ID", "school_demo"), metadata=counts)
        time.sleep(settings.media_worker_interval_seconds)


if __name__ == "__main__":
    run_loop()
