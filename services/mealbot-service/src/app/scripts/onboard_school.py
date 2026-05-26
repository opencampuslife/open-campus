from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.db.connection import get_conn
from app.db.repositories import pilot as pilot_repo
from app.db.repositories.operation_logs import write_operation_log
from app.modules.pilot.config_loader import load_pilot_yaml


def _school_id(config: dict[str, dict[str, str]], override: str | None) -> str:
    candidate = override or config["school"].get("id") or config["school"]["name"]
    normalized = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in candidate.strip())
    return normalized or "pilot_school"


def onboard(config_path: Path, school_override: str | None = None) -> dict[str, object]:
    config = load_pilot_yaml(config_path)
    school_id = _school_id(config, school_override)
    school = config["school"]
    wecom = config["wecom"]
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO schools (school_id, name, wecom_corp_id, wecom_agent_id, status)
            VALUES (%(school_id)s, %(name)s, %(corp_id)s, %(agent_id)s, 'active')
            ON CONFLICT (school_id) DO UPDATE SET
                name = EXCLUDED.name, wecom_corp_id = EXCLUDED.wecom_corp_id,
                wecom_agent_id = EXCLUDED.wecom_agent_id, status = 'active'
            """,
            {
                "school_id": school_id,
                "name": school["name"],
                "corp_id": wecom["corp_id"],
                "agent_id": wecom["agent_id"],
            },
        )
    pilot_repo.upsert_school_config(
        school_id=school_id,
        timezone=school["timezone"],
        callback_url=wecom["callback_url"],
        meal_policy=config["meal"],
        vendor=config["vendor"],
    )
    pilot_repo.ensure_controls(school_id)
    write_operation_log(
        school_id=school_id,
        actor_user_id="onboard_school",
        biz_type="pilot_school",
        biz_id=school_id,
        action="pilot_school.onboarded",
        after={"school_name": school["name"], "timezone": school["timezone"]},
    )
    return {
        "ok": True,
        "school_id": school_id,
        "configured_meal_policy": config["meal"],
        "configured_vendor": {"name": config["vendor"]["name"], "channel": config["vendor"]["channel"]},
        "configured_reminder_rules": {"reminder_worker_enabled": True, "wecom_media_worker_enabled": True},
        "callback_check": {
            "configured": bool(wecom["callback_url"] and wecom["corp_id"] and wecom["agent_id"]),
            "url": wecom["callback_url"],
            "secrets_required_from_environment": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--school-id")
    args = parser.parse_args()
    print(json.dumps(onboard(args.config, args.school_id), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
