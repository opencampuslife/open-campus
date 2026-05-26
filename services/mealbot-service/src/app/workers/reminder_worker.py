from __future__ import annotations

import os
import signal
import sys
import time
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))

sys.path.insert(0, str(os.environ.get("MEALBOT_SRC", ".")))


def run_loop():
    from app.config import load_settings
    from app.db.repositories.worker_heartbeats import heartbeat
    from app.services.reminder_service import process_due_reminders

    worker_id = f"worker-{os.getpid()}"
    settings = load_settings()
    running = True

    def _shutdown(sig, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while running:
        try:
            counts = process_due_reminders(worker_id)
            heartbeat("reminder_worker", school_id=os.environ.get("WECOM_SCHOOL_ID", "school_demo"), metadata=counts)
            if counts["processed"] > 0:
                print(f"{_now_iso()} processed={counts['processed']} sent={counts['sent']} skipped={counts['skipped']} failed={counts['failed']}")
        except Exception:
            import logging
            logging.getLogger("reminder_worker").warning("worker loop error", exc_info=True)
        time.sleep(settings.reminder_worker_interval_seconds)


def _now_iso() -> str:
    return datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S")


if __name__ == "__main__":
    run_loop()
