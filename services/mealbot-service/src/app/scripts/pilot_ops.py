from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from app.modules.pilot.service import (
    export_meal_summary,
    invalidate_vendor_links,
    set_runtime_state,
    unlock_meal,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command, enabled in (("pause", False), ("resume", True)):
        sub = subparsers.add_parser(command)
        sub.add_argument("--school-id", required=True)
        sub.add_argument("--features", default="h5_submissions,reminder_worker,wecom_media_worker")
        sub.set_defaults(enabled=enabled)
    export = subparsers.add_parser("export-summary")
    export.add_argument("--school-id", required=True)
    export.add_argument("--date", required=True)
    export.add_argument("--output", type=Path, required=True)
    invalidate = subparsers.add_parser("invalidate-vendor-links")
    invalidate.add_argument("--school-id", required=True)
    unlock = subparsers.add_parser("unlock-meal")
    unlock.add_argument("--school-id", required=True)
    unlock.add_argument("--lock-id", required=True)
    args = parser.parse_args()
    if args.command in {"pause", "resume"}:
        features = [feature.strip() for feature in args.features.split(",") if feature.strip()]
        result = set_runtime_state(args.school_id, features, args.enabled, "pilot_ops")
    elif args.command == "export-summary":
        result = export_meal_summary(args.school_id, date.fromisoformat(args.date), args.output)
    elif args.command == "invalidate-vendor-links":
        result = {"invalidated": invalidate_vendor_links(args.school_id, "pilot_ops")}
    else:
        result = unlock_meal(args.school_id, args.lock_id, "pilot_ops")
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
