#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROUTE_BRANCH_RE = re.compile(r"\bpath\.(startswith|endswith)\s*\(")
SERVER_RE = re.compile(r"\b(BaseHTTPRequestHandler|ThreadingHTTPServer|HTTPServer)\b")
DEFAULT_GATEWAY_FILE = "services/api-gateway/src/server.py"
DEFAULT_ALLOWED_SERVER_FILE = DEFAULT_GATEWAY_FILE


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()


def check_route_branches(path: Path, root: Path, allow_existing: bool) -> list[str]:
    if not path.exists():
        return []
    errors: list[str] = []
    for line_no, line in enumerate(read_lines(path), start=1):
        if ROUTE_BRANCH_RE.search(line):
            # Existing branches are known migration debt. CI should run this checker
            # in diff mode when possible; full-tree mode defaults to reporting them
            # unless --allow-existing is set.
            if allow_existing:
                continue
            rel = path.relative_to(root).as_posix()
            errors.append(f"{rel}:{line_no}: route branch must be frozen behind contracts/routes.yaml: {line.strip()}")
    return errors


def check_server_definitions(root: Path, allowed_server_file: str) -> list[str]:
    errors: list[str] = []
    allowed = allowed_server_file.replace("\\", "/")
    for path in sorted(root.glob("services/**/*.py")):
        rel = path.relative_to(root).as_posix()
        if rel == allowed:
            continue
        if "/tests/" in rel or rel.startswith("tests/"):
            continue
        for line_no, line in enumerate(read_lines(path), start=1):
            if SERVER_RE.search(line):
                errors.append(f"{rel}:{line_no}: new Python HTTP server primitive is not allowed: {line.strip()}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze Python gateway route growth during Go control-plane migration.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--gateway-file", default=DEFAULT_GATEWAY_FILE)
    parser.add_argument("--allowed-server-file", default=DEFAULT_ALLOWED_SERVER_FILE)
    parser.add_argument(
        "--allow-existing",
        action="store_true",
        help="Allow current route branches in the legacy gateway file. Use this while migrating existing debt.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    gateway_file = root / args.gateway_file

    errors: list[str] = []
    errors.extend(check_route_branches(gateway_file, root, allow_existing=args.allow_existing))
    errors.extend(check_server_definitions(root, args.allowed_server_file))

    if errors:
        for error in errors:
            print(f"GATEWAY FREEZE FAIL: {error}")
        return 1

    print("gateway freeze checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
