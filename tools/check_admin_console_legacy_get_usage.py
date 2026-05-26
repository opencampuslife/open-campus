from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LEGACY_MUTATION_PATTERNS = [
    "/api/admin/ingestion/runs/*/cancel",
    "/api/admin/staging/docs/*/validate",
    "/api/admin/staging/docs/*/approve",
    "/api/admin/staging/docs/*/reject",
    "/api/admin/staging/docs/*/publish",
]

LEGACY_MUTATION_RE = re.compile(
    r"/api/admin/(?:ingestion/runs/[^/]+/cancel|staging/docs/[^/]+/(?:validate|approve|reject|publish))"
)


def check_file(filepath: Path) -> list[str]:
    errors: list[str] = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return errors

    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        match = LEGACY_MUTATION_RE.search(line)
        if not match:
            continue

        path_hit = match.group()
        context_start = max(0, i - 5)
        context = "\n".join(lines[context_start:i + 2])

        has_post = bool(re.search(r'method\s*:\s*["\']POST["\']', context, re.IGNORECASE))
        has_csrf = bool(re.search(r'X-CSRF-Token', context, re.IGNORECASE))
        uses_admin_mutation = bool(re.search(r'adminMutation\s*\(', context))

        if not has_post and not uses_admin_mutation:
            errors.append(
                f"{filepath}:{i}: legacy GET mutation call to {path_hit} - "
                f"must use POST or adminMutation()"
            )

        if has_post and not has_csrf:
            errors.append(
                f"{filepath}:{i}: POST to {path_hit} missing X-CSRF-Token header"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Check admin console for legacy GET mutation usage")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--exit-zero", action="store_true", help="Exit 0 even with findings (for inventory mode)")
    args = parser.parse_args()

    admin_console_src = args.root / "apps" / "admin-console" / "src"

    if not admin_console_src.exists():
        print("SKIP: admin-console/src not found", file=sys.stderr)
        return 0

    tsx_files = sorted(admin_console_src.rglob("*.ts")) + sorted(admin_console_src.rglob("*.tsx"))

    all_errors: list[str] = []
    for filepath in tsx_files:
        all_errors.extend(check_file(filepath))

    if all_errors:
        print(f"Found {len(all_errors)} legacy GET mutation usage(s) in admin console:")
        for err in all_errors:
            print(f"  {err}")
        if args.exit_zero:
            return 0
        return 1

    print(f"OK: {len(tsx_files)} files checked, 0 legacy GET mutations found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
