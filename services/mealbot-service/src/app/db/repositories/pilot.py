from __future__ import annotations

from datetime import date
from typing import Any

from psycopg.types.json import Jsonb

from app.db.connection import get_conn


FEATURE_COLUMNS = {
    "h5_submissions": "h5_submissions_enabled",
    "reminder_worker": "reminder_worker_enabled",
    "wecom_media_worker": "wecom_media_worker_enabled",
}


def upsert_school_config(
    *,
    school_id: str,
    timezone: str,
    callback_url: str,
    meal_policy: dict[str, Any],
    vendor: dict[str, Any],
) -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO pilot_school_configs (school_id, timezone, callback_url, meal_policy_json, vendor_json)
            VALUES (%(school_id)s, %(timezone)s, %(callback_url)s, %(meal_policy)s, %(vendor)s)
            ON CONFLICT (school_id) DO UPDATE SET
                timezone = EXCLUDED.timezone,
                callback_url = EXCLUDED.callback_url,
                meal_policy_json = EXCLUDED.meal_policy_json,
                vendor_json = EXCLUDED.vendor_json
            RETURNING *
            """,
            {
                "school_id": school_id,
                "timezone": timezone,
                "callback_url": callback_url,
                "meal_policy": Jsonb(meal_policy),
                "vendor": Jsonb(vendor),
            },
        ).fetchone()


def ensure_controls(school_id: str, updated_by: str = "onboard_school") -> dict[str, Any]:
    with get_conn() as conn:
        return conn.execute(
            """
            INSERT INTO mealbot_runtime_controls (school_id, updated_by)
            VALUES (%(school_id)s, %(updated_by)s)
            ON CONFLICT (school_id) DO UPDATE SET school_id = EXCLUDED.school_id
            RETURNING *
            """,
            {"school_id": school_id, "updated_by": updated_by},
        ).fetchone()


def get_controls(school_id: str) -> dict[str, Any]:
    row = ensure_controls(school_id)
    return row


def set_features(school_id: str, features: list[str], enabled: bool, updated_by: str) -> dict[str, Any]:
    unknown = sorted(set(features) - FEATURE_COLUMNS.keys())
    if unknown:
        raise ValueError(f"UNKNOWN_FEATURES:{','.join(unknown)}")
    ensure_controls(school_id, updated_by)
    assignments = ", ".join(f"{FEATURE_COLUMNS[feature]} = %({feature})s" for feature in features)
    params: dict[str, Any] = {"school_id": school_id, "updated_by": updated_by}
    params.update({feature: enabled for feature in features})
    with get_conn() as conn:
        return conn.execute(
            f"""UPDATE mealbot_runtime_controls
            SET {assignments}, updated_by = %(updated_by)s
            WHERE school_id = %(school_id)s
            RETURNING *""",
            params,
        ).fetchone()


def is_feature_enabled(school_id: str, feature: str) -> bool:
    column = FEATURE_COLUMNS.get(feature)
    if not column:
        raise ValueError(f"UNKNOWN_FEATURE:{feature}")
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT {column} AS enabled FROM mealbot_runtime_controls WHERE school_id = %(school_id)s",
            {"school_id": school_id},
        ).fetchone()
    return True if not row else bool(row["enabled"])


def status_counts(school_id: str, status_date: date) -> dict[str, Any]:
    with get_conn() as conn:
        orders = conn.execute(
            """
            SELECT
                count(*) FILTER (WHERE action IN ('order', 'add')) AS orders_today,
                count(*) FILTER (WHERE action = 'cancel') AS cancels_today
            FROM meal_orders WHERE school_id = %(school_id)s AND meal_date = %(status_date)s
            """,
            {"school_id": school_id, "status_date": status_date},
        ).fetchone()
        attachments = conn.execute(
            "SELECT count(*) AS count FROM attachments WHERE school_id = %(school_id)s AND created_at::date = %(status_date)s",
            {"school_id": school_id, "status_date": status_date},
        ).fetchone()
        locks = conn.execute(
            "SELECT count(*) AS count FROM meal_locks WHERE school_id = %(school_id)s AND meal_date = %(status_date)s",
            {"school_id": school_id, "status_date": status_date},
        ).fetchone()
        vendor = conn.execute(
            """
            SELECT count(*) FILTER (WHERE status = 'pending') AS pending,
                   count(*) FILTER (WHERE status = 'confirmed') AS confirmed
            FROM vendor_confirmations WHERE school_id = %(school_id)s AND created_at::date = %(status_date)s
            """,
            {"school_id": school_id, "status_date": status_date},
        ).fetchone()
        reminders = conn.execute(
            """
            SELECT count(*) FILTER (WHERE status = 'pending') AS pending,
                   count(*) FILTER (WHERE status = 'failed') AS failed
            FROM reminder_tasks WHERE school_id = %(school_id)s
            """,
            {"school_id": school_id},
        ).fetchone()
        inbound = conn.execute(
            """
            SELECT count(*) FILTER (WHERE status = 'download_pending') AS pending,
                   count(*) FILTER (WHERE status = 'failed') AS failed
            FROM inbound_messages WHERE school_id = %(school_id)s
            """,
            {"school_id": school_id},
        ).fetchone()
    return {
        "orders_today": orders["orders_today"],
        "cancels_today": orders["cancels_today"],
        "attachments_today": attachments["count"],
        "locks_today": locks["count"],
        "vendor_pending": vendor["pending"],
        "vendor_confirmed": vendor["confirmed"],
        "reminders_pending": reminders["pending"],
        "reminders_failed": reminders["failed"],
        "inbound_images_pending": inbound["pending"],
        "inbound_images_failed": inbound["failed"],
    }
