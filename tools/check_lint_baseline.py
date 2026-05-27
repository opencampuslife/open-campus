#!/usr/bin/env python3
"""
Lint baseline checker for ruff and mypy.

Usage:
  python tools/check_lint_baseline.py --mode check   # default: check against baseline
  python tools/check_lint_baseline.py --mode update  # explicit: regenerate baseline
  python tools/check_lint_baseline.py --tool ruff    # single tool only

Rules:
  - check mode: blocks new issues not in baseline; baseline cannot grow.
  - update mode: regenerates baseline (only to shrink or on first run).
  - integrity is separately enforced by tools/check_baseline_integrity.py.

Schema v1 baseline format:
  {
    "schema_version": 1,
    "tool": "ruff",
    "generated_at": "ISO8601",
    "root": ".",
    "issue_count": N,
    "issues": [{"key": "path:code:line", "path": "...", "code": "...", "line": N, "column": N}]
  }
"""

import json
import hashlib
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

SCHEMA_VERSION = 1
BASELINE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "contracts")


def run_ruff():
    result = subprocess.run(
        [
            sys.executable, "-m", "ruff", "check",
            "services/", "tools/", "contracts/",
            "--ignore=E501",
            "--output-format=concise",
        ],
        capture_output=True, text=True, cwd=os.path.join(BASELINE_DIR, ".."),
    )
    issues = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(.+?):(\d+):(\d+): (\w+)", line)
        if m:
            path = m.group(1)
            lineno = int(m.group(2))
            col = int(m.group(3))
            code = m.group(4)
            key = f"{path}:{code}:{lineno}"
            issues.append({
                "key": key,
                "path": path,
                "code": code,
                "line": lineno,
                "column": col,
            })
    return sorted(issues, key=lambda i: i["key"])


def run_mypy():
    result = subprocess.run(
        [
            sys.executable, "-m", "mypy",
            "services/", "tools/",
            "--ignore-missing-imports",
        ],
        capture_output=True, text=True, cwd=os.path.join(BASELINE_DIR, ".."),
    )
    issues = []
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(.+?):(\d+): (?:error|note): (.+)", line)
        if m:
            path = m.group(1)
            lineno = int(m.group(2))
            msg = m.group(3)
            code = _extract_mypy_code(msg)
            key = f"{path}:{code}:{lineno}"
            issues.append({
                "key": key,
                "path": path,
                "code": code,
                "line": lineno,
                "column": None,
                "message": msg,
            })
    return sorted(issues, key=lambda i: i["key"])


def _extract_mypy_code(message):
    m = re.search(r"\[([\w-]+)\]$", message)
    if m:
        return m.group(1)
    return hashlib.sha1(message.encode()).hexdigest()[:8]


def baseline_path(tool):
    return os.path.join(BASELINE_DIR, f"{tool}_baseline.json")


def load_baseline(tool):
    p = baseline_path(tool)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION:
        return data
    if isinstance(data, list):
        return _migrate_v0_to_v1(tool, data)
    return None


def _migrate_v0_to_v1(tool, issues_list):
    """One-shot: convert old flat list to schema v1."""
    issues = []
    for i in issues_list:
        path = i.get("file", "")
        if tool == "ruff":
            code = i.get("rule", "")
            lineno = i.get("line", 0)
            key = f"{path}:{code}:{lineno}"
            issues.append({
                "key": key, "path": path, "code": code,
                "line": lineno, "column": i.get("column", None),
            })
        else:
            code = i.get("code", _extract_mypy_code(i.get("message", "")))
            lineno = i.get("line", 0)
            key = f"{path}:{code}:{lineno}"
            issues.append({
                "key": key, "path": path, "code": code,
                "line": lineno, "column": i.get("column", None),
                "message": i.get("message", ""),
            })
    issues.sort(key=lambda x: x["key"])
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": tool,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": ".",
        "issue_count": len(issues),
        "issues": issues,
    }


def save_baseline(tool, issues):
    p = baseline_path(tool)
    blob = {
        "schema_version": SCHEMA_VERSION,
        "tool": tool,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": ".",
        "issue_count": len(issues),
        "issues": issues,
    }
    with open(p, "w") as f:
        json.dump(blob, f, indent=2)
    print(f"[{tool}] baseline saved: {p} ({len(issues)} issues)")


def check_tool(tool, run_fn):
    current = run_fn()
    baseline = load_baseline(tool)

    if baseline is None:
        print(f"[{tool}] no baseline found — generating with {len(current)} existing issues")
        save_baseline(tool, current)
        print(f"[{tool}] PASS (baseline created)")
        return 0

    baseline_keys = {i["key"] for i in baseline["issues"]}
    current_keys = {i["key"] for i in current}

    new_issues = [i for i in current if i["key"] not in baseline_keys]
    fixed_issues = [i for i in baseline["issues"] if i["key"] not in current_keys]

    if fixed_issues:
        print(f"[{tool}] {len(fixed_issues)} issues resolved (run --mode update to shrink baseline)")

    if new_issues:
        print(f"[{tool}] BLOCKED — {len(new_issues)} new issues not in baseline:")
        for i in new_issues:
            print(f"  {i['key']}")
        print(f"\n[{tool}] Fix the issues above, or run --mode update to baseline them explicitly.")
        return 1

    print(f"[{tool}] PASS — no new issues ({len(current)} current, {len(baseline['issues'])} baseline)")
    return 0


def update(tool, run_fn):
    current = run_fn()
    save_baseline(tool, current)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Lint baseline gate for ruff + mypy")
    p.add_argument("--mode", choices=["check", "update"], default="check",
                   help="check: gate on new issues (default); update: regenerate baseline")
    p.add_argument("--tool", choices=["ruff", "mypy"], help="Check a single tool only")
    args = p.parse_args()

    if args.mode == "update":
        if not args.tool or args.tool == "ruff":
            update("ruff", run_ruff)
        if not args.tool or args.tool == "mypy":
            update("mypy", run_mypy)
        return

    exit_code = 0
    if not args.tool or args.tool == "ruff":
        exit_code |= check_tool("ruff", run_ruff)
    if not args.tool or args.tool == "mypy":
        exit_code |= check_tool("mypy", run_mypy)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
