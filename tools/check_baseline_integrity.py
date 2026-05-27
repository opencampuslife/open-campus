#!/usr/bin/env python3
"""
Baseline integrity checker.

Compares lint baseline files between HEAD and a base ref (e.g. origin/main).
Ensures baseline files cannot grow in a PR; only shrink or stay the same.

Usage:
  python tools/check_baseline_integrity.py --root . [--base-ref origin/main]

  # CI mode — fail if baseline has grown
  python tools/check_baseline_integrity.py --root . --base-ref origin/main

  # Local mode — dry-run against committed state
  python tools/check_baseline_integrity.py --root .

Rules enforced:
  - issue_count may not increase
  - issue keys (path:code:line) may not expand beyond baseline
  - schema_version must not change
  - tool name must not change
  - generated_at may change freely
  - baseline file must exist and be valid
"""

import json
import os
import subprocess
import sys

FILES = [
    "contracts/ruff_baseline.json",
    "contracts/mypy_baseline.json",
]

SCHEMA_VERSION = 1


def load_baseline(root, path):
    full = os.path.join(root, path)
    if not os.path.exists(full):
        return None
    with open(full) as f:
        return json.load(f)


def load_baseline_from_ref(root, path, ref):
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            capture_output=True, text=True, cwd=root,
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception:
        return None


def validate_baseline(blob, path):
    errors = []
    if blob is None:
        errors.append(f"{path}: file missing — run 'python tools/check_lint_baseline.py --mode update'")
        return errors
    if not isinstance(blob, dict):
        errors.append(f"{path}: invalid format — must be a JSON object (schema v1)")
        return errors
    if blob.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{path}: schema_version={blob.get('schema_version')}, expected {SCHEMA_VERSION}")
    if blob.get("tool") not in ("ruff", "mypy"):
        errors.append(f"{path}: unknown tool={blob.get('tool')}")
    if not isinstance(blob.get("issues"), list):
        errors.append(f"{path}: issues must be a list")
    if blob.get("issue_count") != len(blob.get("issues", [])):
        errors.append(
            f"{path}: issue_count={blob.get('issue_count')} disagrees with actual issue count={len(blob.get('issues', []))}"
        )
    for i, iss in enumerate(blob.get("issues", [])):
        if "key" not in iss or "path" not in iss or "code" not in iss or "line" not in iss:
            errors.append(f"{path}: issue[{i}] missing required fields (key, path, code, line)")
            break
    return errors


def check_integrity(root, base_ref, strict=False):
    exit_code = 0

    for path in FILES:
        head = load_baseline(root, path)
        base = load_baseline_from_ref(root, path, base_ref) if base_ref else None

        if head is None:
            print(f"[FAIL] {path}: missing in working tree")
            exit_code = 1
            continue

        format_errors = validate_baseline(head, path)
        if format_errors:
            for e in format_errors:
                print(f"[FAIL] {e}")
            exit_code = 1
            continue

        if base is None:
            print(f"[SKIP] {path}: no baseline in base ref (first commit?)")
            continue

        format_errors = validate_baseline(base, path)
        if format_errors:
            if strict:
                print(f"[FAIL] {path}: baseline in base ref has format errors — strict mode requires valid base")
                for e in format_errors:
                    print(f"  {e}")
                exit_code = 1
                continue
            print(f"[WARN] {path}: baseline in base ref has legacy/v0 format — integrity comparison SKIPPED")
            print("  TODO: Remove this skip after first schema v1 baseline commit lands on main.")
            print("  Run with --strict to enforce format validation on base ref.")
            continue

        if head["schema_version"] != base["schema_version"]:
            print(f"[FAIL] {path}: schema_version changed from {base['schema_version']} to {head['schema_version']}")
            exit_code = 1

        if head["tool"] != base["tool"]:
            print(f"[FAIL] {path}: tool changed from {base['tool']} to {head['tool']}")
            exit_code = 1

        head_count = head["issue_count"]
        base_count = base["issue_count"]

        base_keys = {i["key"] for i in base["issues"]}
        head_keys = {i["key"] for i in head["issues"]}

        added = head_keys - base_keys
        removed = base_keys - head_keys

        if added:
            print(f"[FAIL] {path}: {len(added)} issue keys ADDED (not allowed in PR):")
            for k in sorted(added)[:10]:
                print(f"  + {k}")
            if len(added) > 10:
                print(f"  ... and {len(added) - 10} more")
            exit_code = 1

        if removed:
            print(f"[INFO] {path}: {len(removed)} issues resolved (allowed)")

        if head_count > base_count and not added:
            print(f"[FAIL] {path}: issue_count increased from {base_count} to {head_count} but no keys differ")
            exit_code = 1

        if not added:
            print(f"[PASS] {path}: baseline integrity OK ({head_count} issues)")

    return exit_code


def main():
    import argparse
    p = argparse.ArgumentParser(description="Baseline integrity checker")
    p.add_argument("--root", default=".", help="Repo root directory")
    p.add_argument("--base-ref", default=None, help="Git base ref to compare against (e.g. origin/main)")
    p.add_argument("--strict", action="store_true",
                   help="Fail on legacy/v0 base format instead of skipping")
    args = p.parse_args()

    root = os.path.abspath(args.root)
    sys.exit(check_integrity(root, args.base_ref, strict=args.strict))


if __name__ == "__main__":
    main()
