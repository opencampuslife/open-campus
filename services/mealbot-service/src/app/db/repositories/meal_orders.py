from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from app.db.connection import get_conn


def create_or_update_order(data: dict[str, Any]) -> dict[str, Any]:
    sql = """
    INSERT INTO meal_orders (
        order_id, school_id, student_id, class_id, meal_date, meal_type, action,
        reason, dietary_note, submitted_by_wecom_userid, status
    )
    VALUES (
        %(order_id)s, %(school_id)s, %(student_id)s, %(class_id)s,
        %(meal_date)s, %(meal_type)s, %(action)s,
        %(reason)s, %(dietary_note)s, %(submitted_by_wecom_userid)s,
        %(status)s
    )
    ON CONFLICT (student_id, meal_date, meal_type, action)
    DO UPDATE SET
        reason = EXCLUDED.reason,
        dietary_note = EXCLUDED.dietary_note,
        status = EXCLUDED.status,
        updated_at = now()
    RETURNING *;
    """
    data.setdefault("order_id", "")
    data.setdefault("school_id", "")
    data.setdefault("student_id", "")
    data.setdefault("class_id", "")
    data.setdefault("meal_date", date.today())
    data.setdefault("meal_type", "lunch")
    data.setdefault("action", "order")
    data.setdefault("reason", None)
    data.setdefault("dietary_note", None)
    data.setdefault("submitted_by_wecom_userid", None)
    data.setdefault("status", "submitted")
    with get_conn() as conn:
        return conn.execute(sql, data).fetchone()


def get_order(order_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM meal_orders WHERE order_id = %(order_id)s",
            {"order_id": order_id},
        ).fetchone()


def list_orders_for_student(student_id: str, meal_date: date | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM meal_orders WHERE student_id = %(student_id)s"
    params: dict[str, Any] = {"student_id": student_id}
    if meal_date:
        sql += " AND meal_date = %(meal_date)s"
        params["meal_date"] = meal_date
    sql += " ORDER BY created_at DESC"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def list_orders_for_school(school_id: str, meal_date: date | None = None, meal_type: str | None = None) -> list[dict[str, Any]]:
    sql = "SELECT * FROM meal_orders WHERE school_id = %(school_id)s"
    params: dict[str, Any] = {"school_id": school_id}
    if meal_date:
        sql += " AND meal_date = %(meal_date)s"
        params["meal_date"] = meal_date
    if meal_type:
        sql += " AND meal_type = %(meal_type)s"
        params["meal_type"] = meal_type
    sql += " ORDER BY created_at DESC"
    with get_conn() as conn:
        return conn.execute(sql, params).fetchall()


def update_order_status(order_id: str, status: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "UPDATE meal_orders SET status = %(status)s WHERE order_id = %(order_id)s RETURNING *",
            {"order_id": order_id, "status": status},
        ).fetchone()


def cancel_order(order_id: str) -> dict[str, Any] | None:
    return update_order_status(order_id, "cancelled")


def lock_orders_for_summary(school_id: str, meal_date: date, meal_type: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """UPDATE meal_orders
            SET status = 'locked'
            WHERE school_id = %(school_id)s
              AND meal_date = %(meal_date)s
              AND meal_type = %(meal_type)s
              AND status = 'submitted'
            RETURNING *""",
            {"school_id": school_id, "meal_date": meal_date, "meal_type": meal_type},
        ).fetchall()


def get_summary(school_id: str, meal_date: date) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT
                meal_type, action, count(*) as cnt
            FROM meal_orders
            WHERE school_id = %(school_id)s AND meal_date = %(meal_date)s
            GROUP BY meal_type, action
            ORDER BY meal_type, action""",
            {"school_id": school_id, "meal_date": meal_date},
        ).fetchall()
