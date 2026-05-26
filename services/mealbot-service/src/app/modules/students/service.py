from __future__ import annotations

from typing import Any

from app.db.repositories import students as repo


def get_students_by_parent(wecom_userid: str, school_id: str) -> list[dict[str, Any]]:
    return repo.get_students_by_parent_wecom_userid(wecom_userid, school_id)


def get_student(student_id: str) -> dict[str, Any] | None:
    return repo.get_student(student_id)


def validate_student_access(student_id: str, wecom_userid: str, school_id: str) -> bool:
    student = repo.get_student(student_id)
    if not student:
        return False
    if student["school_id"] != school_id:
        return False
    return student.get("parent_userid") == wecom_userid
