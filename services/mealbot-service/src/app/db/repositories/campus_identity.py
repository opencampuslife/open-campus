from __future__ import annotations

from typing import Any

from app.db.connection import get_conn


def resolve_wecom_identity(wecom_userid: str, school_id: str) -> dict[str, Any] | None:
    """Map an authenticated WeCom member to a scoped campus identity."""
    with get_conn() as conn:
        staff = conn.execute(
            """
            SELECT user_id, school_id, wecom_userid, role, class_id
            FROM campus_users
            WHERE school_id = %(school_id)s
              AND wecom_userid = %(wecom_userid)s
              AND status = 'active'
            """,
            {"school_id": school_id, "wecom_userid": wecom_userid},
        ).fetchone()
        if staff:
            class_id = str(staff.get("class_id") or "")
            return {
                "user_id": staff["user_id"],
                "wecom_userid": staff["wecom_userid"],
                "role": staff["role"],
                "campus": staff["school_id"],
                "school_id": staff["school_id"],
                "class_id": class_id,
                "class_ids": [class_id] if class_id else [],
                "auth_level": "wecom_oauth",
            }

        parent_students = conn.execute(
            """
            SELECT student_id
            FROM students
            WHERE school_id = %(school_id)s
              AND parent_userid = %(wecom_userid)s
              AND status = 'active'
            ORDER BY student_id
            LIMIT 1
            """,
            {"school_id": school_id, "wecom_userid": wecom_userid},
        ).fetchone()
        if not parent_students:
            return None
        return {
            "user_id": wecom_userid,
            "wecom_userid": wecom_userid,
            "role": "parent_or_student_h5",
            "campus": school_id,
            "school_id": school_id,
            "student_id": parent_students["student_id"],
            "auth_level": "wecom_oauth",
        }
