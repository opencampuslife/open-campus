#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

FORBIDDEN_RE = re.compile(r"\bsys\.path\.(append|insert|extend)\s*\(")
DEFAULT_GLOBS = ("services/*/src/**/*.py",)
DEFAULT_ALLOWED_SUFFIXES = (
    "tests/conftest.py",
    "test/conftest.py",
)


def iter_python_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        files.update(p for p in root.glob(pattern) if p.is_file())
    return sorted(files)


def is_allowed(path: Path, root: Path, extra_allowed: set[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    if rel in extra_allowed:
        return True
    return any(rel.endswith(suffix) for suffix in DEFAULT_ALLOWED_SUFFIXES)


def check_file(path: Path) -> list[tuple[int, str]]:
    findings: list[tuple[int, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")
    for line_no, line in enumerate(text.splitlines(), start=1):
        if FORBIDDEN_RE.search(line):
            findings.append((line_no, line.strip()))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail on sys.path mutations in production service source.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--glob",
        action="append",
        dest="globs",
        help="Glob to scan relative to root. Can be repeated. Defaults to services/*/src/**/*.py",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        help="Exact repository-relative path allowed to contain sys.path mutations.",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        help="Path to JSON allowlist file with entries [{\"path\": \"services/...\", ...}]",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    patterns = tuple(args.globs or DEFAULT_GLOBS)
    allowed = {p.replace("\\", "/") for p in args.allow}

    if args.allowlist and args.allowlist.exists():
        import json
        data = json.loads(args.allowlist.read_text(encoding="utf-8"))
        for entry in data.get("entries", []):
            allowed.add(entry["path"].replace("\\", "/"))

    errors: list[str] = []
    for path in iter_python_files(root, patterns):
        if is_allowed(path, root, allowed):
            continue
        for line_no, snippet in check_file(path):
            rel = path.relative_to(root).as_posix()
            errors.append(f"{rel}:{line_no}: forbidden sys.path mutation: {snippet}")

    if errors:
        for error in errors:
            print(f"PACKAGE BOUNDARY FAIL: {error}")
        return 1

    print("package boundary checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
