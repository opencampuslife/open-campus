from __future__ import annotations

import os
import uuid

import psycopg


def scalar(url: str, role: str | None, school_id: str, class_id: str, query: str) -> int:
    with psycopg.connect(url) as conn:
        with conn.transaction():
            if role:
                conn.execute("SELECT set_config('app.role', %s, true)", (role,))
                conn.execute("SELECT set_config('app.school_id', %s, true)", (school_id,))
                conn.execute("SELECT set_config('app.class_id', %s, true)", (class_id,))
            return int(conn.execute(query).fetchone()[0])


def main() -> int:
    admin_url = os.environ["DATABASE_URL_ADMIN"]
    staff_url = os.environ["DATABASE_URL_STAFF"]
    suffix = uuid.uuid4().hex[:10]
    school = f"rls_mod_{suffix}"
    own_class = f"own_{suffix}"
    other_class = f"other_{suffix}"
    with psycopg.connect(admin_url) as conn:
        conn.execute("INSERT INTO schools (school_id, name) VALUES (%s, 'RLS module school')", (school,))
        conn.execute(
            "INSERT INTO classes (class_id, school_id, grade, name) VALUES (%s, %s, 'G3', 'Own'), (%s, %s, 'G3', 'Other')",
            (own_class, school, other_class, school),
        )
        conn.execute(
            """
            INSERT INTO collection_tasks (task_id, school_id, class_id, title, material_type, deadline_at, created_by)
            VALUES (%s, %s, %s, 'Own task', 'form', now(), 'teacher'), (%s, %s, %s, 'Other task', 'form', now(), 'teacher')
            """,
            (f"task_own_{suffix}", school, own_class, f"task_other_{suffix}", school, other_class),
        )
        conn.execute(
            """
            INSERT INTO score_batches (batch_id, school_id, class_id, exam_name, subject, max_score, created_by)
            VALUES (%s, %s, %s, 'Exam', 'Math', 100, 'teacher')
            """,
            (f"score_other_{suffix}", school, other_class),
        )
        conn.commit()
    try:
        own_visible = scalar(staff_url, "head_teacher", school, own_class, f"SELECT count(*) FROM collection_tasks WHERE school_id = '{school}'")
        if own_visible != 1:
            print(f"DB FAIL: head_teacher class isolation expected 1, got {own_visible}")
            return 1
        score_hidden = scalar(staff_url, "head_teacher", school, own_class, f"SELECT count(*) FROM score_batches WHERE school_id = '{school}'")
        if score_hidden != 0:
            print(f"DB FAIL: head_teacher leaked other class scores: {score_hidden}")
            return 1
        fail_closed = scalar(staff_url, None, school, own_class, f"SELECT count(*) FROM collection_tasks WHERE school_id = '{school}'")
        if fail_closed != 0:
            print(f"DB FAIL: module scope without app settings should fail closed: {fail_closed}")
            return 1
        print("campus modules live RLS tests: OK")
        return 0
    finally:
        with psycopg.connect(admin_url) as conn:
            conn.execute("DELETE FROM schools WHERE school_id = %s", (school,))
            conn.commit()


if __name__ == "__main__":
    raise SystemExit(main())
