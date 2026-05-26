from __future__ import annotations

import os
import re
import subprocess
import sys
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "db-policy-service"
MIGRATIONS = SERVICE / "migrations"
FIXTURES = SERVICE / "fixtures"
PSQL = SERVICE / "scripts" / "psql.sh"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Require DATABASE_URL_ADMIN and run live PostgreSQL RLS tests")
    args = parser.parse_args()

    static_errors = run_static_checks()
    if static_errors:
        for error in static_errors:
            print(f"STATIC FAIL: {error}")
        return 1

    db_url = os.environ.get("DATABASE_URL_ADMIN")
    if not db_url:
        if args.live:
            print("DATABASE_URL_ADMIN is required for --live")
            return 1
        print("db policy static checks: OK")
        print("DATABASE_URL_ADMIN not set; skipped live PostgreSQL RLS tests")
        return 0

    return run_live_tests(db_url)


def run_static_checks() -> list[str]:
    errors: list[str] = []
    sql = "\n".join(path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql")))

    required = [
        "ALTER TABLE knowledge_docs ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE knowledge_docs FORCE ROW LEVEL SECURITY",
        "ALTER TABLE knowledge_chunks ENABLE ROW LEVEL SECURITY",
        "ALTER TABLE knowledge_chunks FORCE ROW LEVEL SECURITY",
        "WITH (security_barrier = true)",
        "ALTER VIEW v_accessible_knowledge_chunks OWNER TO gaokao_rls_reader",
        "GRANT SELECT ON knowledge_chunks TO gaokao_rls_reader",
        "SECURITY INVOKER",
        "REVOKE ALL ON knowledge_docs FROM gaokao_api_public",
        "REVOKE ALL ON knowledge_chunks FROM gaokao_api_public",
        "GRANT EXECUTE ON FUNCTION search_accessible_chunks(TEXT, INT) TO gaokao_api_public",
    ]
    for needle in required:
        if needle not in sql:
            errors.append(f"missing required SQL: {needle}")

    if "SECURITY DEFINER" in sql:
        errors.append("search or policy SQL must not use SECURITY DEFINER")

    if re.search(r"SET\s+app\.", sql, flags=re.IGNORECASE):
        errors.append("migrations must not use global SET app.*; use SET LOCAL in request transactions")

    return errors


def run_live_tests(db_url: str) -> int:
    public_url = os.environ.get("DATABASE_URL_PUBLIC", "postgresql://gaokao_api_public:postgres@localhost:54329/gaokao_agent_test")
    staff_url = os.environ.get("DATABASE_URL_STAFF", "postgresql://gaokao_api_staff:postgres@localhost:54329/gaokao_agent_test")
    files = [
        *sorted(MIGRATIONS.glob("*.sql")),
        FIXTURES / "public_chunks.sql",
        FIXTURES / "protected_chunks.sql",
        FIXTURES / "internal_chunks.sql",
        FIXTURES / "admin_chunks.sql",
        FIXTURES / "campus_demo.sql",
    ]
    for file in files:
        run_psql(db_url, file)

    checks = [
        ("parent internal count", public_url, "parent", "SELECT COUNT(*) FROM v_accessible_knowledge_chunks WHERE visibility = 'internal';", "0"),
        (
            "parent direct internal doc id",
            public_url,
            "parent",
            "SELECT COUNT(*) FROM v_accessible_knowledge_chunks WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';",
            "0",
        ),
        (
            "student search sales script",
            public_url,
            "student",
            "SELECT COUNT(*) FROM search_accessible_chunks('家长嫌贵', 10) WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';",
            "0",
        ),
        (
            "sales search sales script",
            staff_url,
            "sales",
            "SELECT COUNT(*) FROM search_accessible_chunks('优惠底价', 10) WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';",
            "1",
        ),
        (
            "sales cannot search admin",
            staff_url,
            "sales",
            "SELECT COUNT(*) FROM search_accessible_chunks('后台策略', 10) WHERE chunk_id = 'admin_redline_rules_2026::chunk_001';",
            "0",
        ),
        (
            "unset session context fails closed",
            public_url,
            None,
            "SELECT COUNT(*) FROM search_accessible_chunks('学费', 10);",
            "0",
        ),
        (
            "sales cross-campus isolation",
            staff_url,
            "sales",
            "SELECT COUNT(*) FROM search_accessible_chunks('优惠底价', 10) WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';",
            "0",
            "beijing",
        ),
    ]
    for check in checks:
        name, check_url, role, query, expected = check[:5]
        campus = check[5] if len(check) > 5 else "zhengzhou"
        actual = run_scalar(check_url, role, query, campus=campus)
        if actual != expected:
            print(f"DB FAIL: {name}: expected {expected}, got {actual}")
            return 1

    if not run_expect_error(public_url, "SELECT * FROM knowledge_chunks LIMIT 1;", "permission denied"):
        print("DB FAIL: gaokao_api_public should not SELECT knowledge_chunks base table")
        return 1

    public_view_count = run_scalar_as_url(
        public_url,
        "parent",
        "SELECT COUNT(*) FROM v_accessible_knowledge_chunks WHERE visibility = 'internal';",
    )
    if public_view_count != "0":
        print(f"DB FAIL: security_invoker view leaked internal rows to public role: {public_view_count}")
        return 1

    if not run_connection_reuse_test(staff_url):
        return 1

    campus_checks = [
        (
            "head teacher sees own class leave",
            staff_url,
            "head_teacher",
            "SELECT COUNT(*) FROM leave_requests WHERE leave_id = 'leave_demo_001';",
            "1",
            {"school_id": "school_demo", "class_id": "class_g7_1"},
        ),
        (
            "logistics cannot see leave details",
            staff_url,
            "logistics_staff",
            "SELECT COUNT(*) FROM leave_requests WHERE leave_id = 'leave_demo_001';",
            "0",
            {"school_id": "school_demo"},
        ),
        (
            "vendor token sees delivery row",
            public_url,
            "vendor_link_user",
            "SELECT COUNT(*) FROM delivery_confirmations WHERE delivery_id = 'delivery_20260525';",
            "1",
            {"vendor_token_hash": "vendor_token_hash_demo"},
        ),
        (
            "vendor without token fail closed",
            public_url,
            "vendor_link_user",
            "SELECT COUNT(*) FROM delivery_confirmations WHERE delivery_id = 'delivery_20260525';",
            "0",
            {},
        ),
        (
            "parent sees own leave only with student scope",
            public_url,
            "parent_or_student_h5",
            "SELECT COUNT(*) FROM leave_requests WHERE leave_id = 'leave_demo_001';",
            "1",
            {"student_id": "student_demo_001"},
        ),
    ]
    for name, check_url, role, query, expected, settings in campus_checks:
        actual = run_scalar(check_url, role, query, extra_settings=settings)
        if actual != expected:
            print(f"DB FAIL: {name}: expected {expected}, got {actual}")
            return 1

    print("db policy live RLS tests: OK")
    return 0


def run_psql(db_url: str, file: Path) -> None:
    subprocess.run([str(PSQL), db_url, "-v", "ON_ERROR_STOP=1", "-f", str(file)], check=True)


def run_scalar(
    db_url: str,
    role: str | None,
    query: str,
    campus: str = "zhengzhou",
    extra_settings: dict[str, str] | None = None,
) -> str:
    set_context = ""
    if role is not None:
        set_context = f"""
SET LOCAL app.role = '{role}';
SET LOCAL app.campus = '{campus}';
"""
    if extra_settings:
        for key, value in extra_settings.items():
            set_context += f"SET LOCAL app.{key} = '{value}';\n"
    sql = f"""
BEGIN;
{set_context}
{query}
ROLLBACK;
"""
    return run_sql_scalar(db_url, sql)


def run_scalar_as_url(db_url: str, role: str, query: str, campus: str = "zhengzhou") -> str:
    return run_scalar(db_url, role, query, campus=campus)


def run_sql_scalar(db_url: str, sql: str) -> str:
    result = subprocess.run(
        [str(PSQL), db_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    rows = [line.strip() for line in result.stdout.splitlines() if line.strip() and line.strip() not in {"BEGIN", "ROLLBACK"}]
    return rows[-1] if rows else ""


def run_expect_error(db_url: str, query: str, expected_substring: str) -> bool:
    result = subprocess.run(
        [str(PSQL), db_url, "-v", "ON_ERROR_STOP=1", "-c", query],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    combined = f"{result.stdout}\n{result.stderr}".lower()
    return result.returncode != 0 and expected_substring.lower() in combined


def run_connection_reuse_test(db_url: str) -> bool:
    sql = """
BEGIN;
SET LOCAL app.role = 'sales';
SET LOCAL app.campus = 'zhengzhou';
SELECT 'sales_internal=' || COUNT(*) FROM search_accessible_chunks('优惠底价', 10)
WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';
COMMIT;

BEGIN;
SET LOCAL app.role = 'parent';
SET LOCAL app.campus = 'zhengzhou';
SELECT 'parent_internal=' || COUNT(*) FROM search_accessible_chunks('优惠底价', 10)
WHERE chunk_id = 'sales_price_sensitive_2026::chunk_001';
COMMIT;

BEGIN;
SELECT 'unset_context=' || COUNT(*) FROM search_accessible_chunks('学费', 10);
ROLLBACK;
"""
    result = subprocess.run(
        [str(PSQL), db_url, "-v", "ON_ERROR_STOP=1", "-At", "-c", sql],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    rows = {line.strip() for line in result.stdout.splitlines() if "=" in line}
    expected = {"sales_internal=1", "parent_internal=0", "unset_context=0"}
    if not expected.issubset(rows):
        print(f"DB FAIL: connection reuse SET LOCAL isolation failed. expected {expected}, got {rows}")
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
