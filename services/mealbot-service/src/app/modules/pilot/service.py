from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from app.db.connection import get_conn
from app.db.repositories import pilot as pilot_repo
from app.db.repositories.operation_logs import write_operation_log


def pilot_status(school_id: str, status_date: date) -> dict[str, Any]:
    controls = pilot_repo.get_controls(school_id)
    mealbot = pilot_repo.status_counts(school_id, status_date)
    with get_conn() as conn:
        db_ok = conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1
        heartbeats = {
            row["worker_name"]: row
            for row in conn.execute(
                "SELECT * FROM worker_heartbeats WHERE school_id = %(school_id)s",
                {"school_id": school_id},
            ).fetchall()
        }
        callback_failures = conn.execute(
            """
            SELECT count(*) AS count FROM operation_logs
            WHERE school_id = %(school_id)s
              AND action = 'wecom_callback.invalid_signature'
              AND created_at > now() - interval '1 day'
            """,
            {"school_id": school_id},
        ).fetchone()["count"]
    workers_ok = all(
        controls[key] is False or name in heartbeats
        for key, name in (
            ("reminder_worker_enabled", "reminder_worker"),
            ("wecom_media_worker_enabled", "wecom_media_worker"),
        )
    )
    return {
        "ok": True,
        "school_id": school_id,
        "date": status_date.isoformat(),
        "mealbot": mealbot,
        "controls": {
            "h5_submissions_enabled": controls["h5_submissions_enabled"],
            "reminder_worker_enabled": controls["reminder_worker_enabled"],
            "wecom_media_worker_enabled": controls["wecom_media_worker_enabled"],
        },
        "health": {
            "db": "ok" if db_ok else "error",
            "workers": "ok" if workers_ok else "waiting_for_heartbeat",
            "wecom_callback": "ok" if callback_failures == 0 else "signature_rejections_seen",
        },
    }


def set_runtime_state(school_id: str, features: list[str], enabled: bool, actor: str) -> dict[str, Any]:
    result = pilot_repo.set_features(school_id, features, enabled, actor)
    write_operation_log(
        school_id=school_id,
        actor_user_id=actor,
        biz_type="pilot_control",
        biz_id=school_id,
        action="pilot.resumed" if enabled else "pilot.paused",
        after={"features": features, "enabled": enabled},
    )
    return result


def export_meal_summary(school_id: str, meal_date: date, output_path: Path) -> dict[str, Any]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT mo.meal_date, mo.meal_type, mo.action, mo.status,
                   mo.student_id, s.student_no, s.name AS student_name,
                   c.name AS class_name, mo.dietary_note
            FROM meal_orders mo
            JOIN students s ON s.student_id = mo.student_id
            JOIN classes c ON c.class_id = mo.class_id
            WHERE mo.school_id = %(school_id)s AND mo.meal_date = %(meal_date)s
            ORDER BY mo.meal_type, c.name, s.student_no, mo.action
            """,
            {"school_id": school_id, "meal_date": meal_date},
        ).fetchall()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        "meal_date", "meal_type", "action", "status", "student_id",
        "student_no", "student_name", "class_name", "dietary_note",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({column: row.get(column, "") for column in columns} for row in rows)
    write_operation_log(
        school_id=school_id,
        actor_user_id="pilot_ops",
        biz_type="meal_summary_export",
        biz_id=f"{school_id}:{meal_date.isoformat()}",
        action="meal_summary.exported",
        after={"rows": len(rows), "date": meal_date.isoformat()},
    )
    return {"school_id": school_id, "date": meal_date.isoformat(), "rows": len(rows), "output": str(output_path)}


def invalidate_vendor_links(school_id: str, actor: str) -> int:
    with get_conn() as conn:
        rows = conn.execute(
            """
            UPDATE vendor_confirmations SET status = 'expired'
            WHERE school_id = %(school_id)s AND status = 'pending'
            RETURNING confirmation_id
            """,
            {"school_id": school_id},
        ).fetchall()
    write_operation_log(
        school_id=school_id, actor_user_id=actor, biz_type="vendor_confirmation",
        biz_id=school_id, action="vendor_confirmation.invalidated_all", after={"count": len(rows)},
    )
    return len(rows)


def unlock_meal(school_id: str, lock_id: str, actor: str) -> dict[str, Any]:
    with get_conn() as conn:
        lock = conn.execute(
            "DELETE FROM meal_locks WHERE school_id = %(school_id)s AND lock_id = %(lock_id)s RETURNING *",
            {"school_id": school_id, "lock_id": lock_id},
        ).fetchone()
        if not lock:
            raise ValueError("MEAL_LOCK_NOT_FOUND")
        conn.execute(
            """
            UPDATE meal_orders SET status = 'submitted'
            WHERE school_id = %(school_id)s AND meal_date = %(meal_date)s
              AND meal_type = %(meal_type)s AND status = 'locked'
            """,
            {"school_id": school_id, "meal_date": lock["meal_date"], "meal_type": lock["meal_type"]},
        )
    write_operation_log(
        school_id=school_id, actor_user_id=actor, biz_type="meal_lock",
        biz_id=lock_id, action="meal_lock.manually_unlocked", after={"status": "removed"},
    )
    return lock
