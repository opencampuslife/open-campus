from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SERVICE = ROOT / "services" / "db-policy-service"
MIGRATIONS = SERVICE / "migrations"
FIXTURES = SERVICE / "fixtures"
PSQL = SERVICE / "scripts" / "psql.sh"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixtures", action="store_true", help="Also load sample fixture data")
    args = parser.parse_args()

    db_url = os.environ.get("DATABASE_URL_ADMIN")
    if not db_url:
        raise SystemExit("DATABASE_URL_ADMIN is required")

    files = list(sorted(MIGRATIONS.glob("*.sql")))
    if args.fixtures:
        files.extend(
            [
                FIXTURES / "public_chunks.sql",
                FIXTURES / "protected_chunks.sql",
                FIXTURES / "internal_chunks.sql",
                FIXTURES / "admin_chunks.sql",
                FIXTURES / "campus_demo.sql",
            ]
        )

    for file in files:
        subprocess.run([str(PSQL), db_url, "-v", "ON_ERROR_STOP=1", "-f", str(file)], check=True)
        print(f"applied {file.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
