from __future__ import annotations

import os
import signal
import sys
import time

sys.path.insert(0, str(os.environ.get("MEALBOT_SRC", ".")))


def run_loop() -> None:
    from app.config import load_settings
    from app.db.repositories.worker_heartbeats import heartbeat
    from app.modules.campus.automation import process_ocr_jobs

    worker_id = f"campus-ocr-{os.getpid()}"
    running = True

    def shutdown(sig, frame):  # type: ignore[no-untyped-def]
        del sig, frame
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    interval = max(2, load_settings().media_worker_interval_seconds)
    while running:
        try:
            counts = process_ocr_jobs(worker_id)
            heartbeat("campus_ocr_worker", school_id=os.environ.get("WECOM_SCHOOL_ID", "school_demo"), metadata=counts)
        except Exception:
            import logging
            logging.getLogger("campus_ocr_worker").warning("worker loop error", exc_info=True)
        time.sleep(interval)


if __name__ == "__main__":
    run_loop()
