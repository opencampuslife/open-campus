from __future__ import annotations

from typing import Any

from app.db.connection import get_conn


def get_student(student_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE student_id = %(student_id)s",
            {"student_id": student_id},
        ).fetchone()


def get_students_by_parent_wecom_userid(wecom_userid: str, school_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE parent_userid = %(wecom_userid)s AND school_id = %(school_id)s",
            {"wecom_userid": wecom_userid, "school_id": school_id},
        ).fetchall()


def get_students_by_parent_with_class(wecom_userid: str, school_id: str) -> list[dict[str, Any]]:
    sql = """
    SELECT s.student_id, s.name, s.student_no, s.parent_userid,
           s.class_id, c.name AS class_name, c.grade,
           s.school_id, s.status
    FROM students s
    LEFT JOIN classes c ON s.class_id = c.class_id
    WHERE s.parent_userid = %(wecom_userid)s
      AND s.school_id = %(school_id)s
      AND s.status = 'active'
    ORDER BY s.name
    """
    with get_conn() as conn:
        return conn.execute(sql, {"wecom_userid": wecom_userid, "school_id": school_id}).fetchall()


def get_students_by_school(school_id: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM students WHERE school_id = %(school_id)s ORDER BY class_id, name",
            {"school_id": school_id},
        ).fetchall()
