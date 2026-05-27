#!/usr/bin/env python3
"""Inventory Python service packaging readiness across services/*.

Generates a machine-readable report: which services have src/, tests/,
pyproject.toml, requirements.txt; which are exercised via Makefile/CI;
which are high-sensitivity; and a rough top-level-import scan.

Usage:
    python tools/inventory_python_services.py --root . [--output reports/python_service_inventory.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

SERVICE_DIR = "services"
SKIP_DIRS = {"uploads"}  # not a service
NON_PYTHON_PATTERNS = {"package.json"}  # Node/TS services

IMPORT_RE = re.compile(r"^(?:from|import)\s+(\w+)", re.MULTILINE)
MAKEFILE_REF_RE = re.compile(r"services/([a-z\-]+)/")
CI_SVC_RE = re.compile(r"services/([a-z\-]+)/")


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def scan_imports(service_root: Path) -> dict[str, set[str]]:
    """Return {file_relpath: set_of_top_level_modules} for Python files under src/."""
    results: dict[str, set[str]] = {}
    src = service_root / "src"
    if not src.is_dir():
        return results
    for py_file in sorted(src.rglob("*.py")):
        if py_file.name.startswith("__"):
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            text = py_file.read_text(encoding="utf-8", errors="replace")
        mods = set()
        for m in IMPORT_RE.finditer(text):
            candidate = m.group(1)
            if candidate not in ("__future__",):
                mods.add(candidate)
        if mods:
            results[py_file.relative_to(src).as_posix()] = mods
    return results


def aggregate_top_imports(file_imports: dict[str, set[str]], top_n: int = 15) -> list[tuple[str, int]]:
    counter: defaultdict[str, int] = defaultdict(int)
    for mods in file_imports.values():
        for m in mods:
            counter[m] += 1
    return sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:top_n]


def load_makefile_refs(root: Path) -> set[str]:
    makefile = root / "Makefile"
    if not makefile.exists():
        return set()
    text = _read_file(makefile)
    return {m.group(1) for m in MAKEFILE_REF_RE.finditer(text)}


def load_ci_refs(root: Path) -> set[str]:
    svc_set: set[str] = set()
    workflows = root / ".github" / "workflows"
    if not workflows.is_dir():
        return svc_set
    for yml in workflows.glob("*.yml"):
        text = _read_file(yml)
        for m in CI_SVC_RE.finditer(text):
            svc_set.add(m.group(1))
    return svc_set


def load_ownership(root: Path) -> dict[str, dict]:
    ownership_file = root / "contracts" / "service_ownership.json"
    if not ownership_file.exists():
        return {}
    data = json.loads(_read_file(ownership_file))
    return {s["name"]: s for s in data.get("services", [])}


def inventory(root: Path) -> list[dict]:
    services_dir = root / SERVICE_DIR
    makefile_refs = load_makefile_refs(root)
    ci_refs = load_ci_refs(root)
    ownership = load_ownership(root)

    results: list[dict] = []
    for svc_dir in sorted(services_dir.iterdir()):
        if not svc_dir.is_dir():
            continue
        name = svc_dir.name
        if name in SKIP_DIRS:
            continue

        has_src = (svc_dir / "src").is_dir()
        has_tests = (svc_dir / "tests").is_dir()
        has_pyproject = (svc_dir / "pyproject.toml").exists()
        has_requirements = (svc_dir / "requirements.txt").exists()
        has_setup_py = (svc_dir / "setup.py").exists()
        has_setup_cfg = (svc_dir / "setup.cfg").exists()
        has_package_json = (svc_dir / "package.json").exists()

        py_file_count = len(list(svc_dir.rglob("*.py")))
        test_file_count = len(list(
            p for p in svc_dir.rglob("*.py")
            if "test" in p.name.lower()
        )) if has_tests else 0

        is_python = has_src or py_file_count > 0
        is_node = has_package_json
        runtime = "python" if is_python and not is_node else "node" if is_node else "unknown"
        if not is_python and not is_node:
            runtime = "unknown"

        file_imports: dict[str, set[str]] = {}
        top_imports: list[tuple[str, int]] = []
        if is_python and has_src:
            file_imports = scan_imports(svc_dir)
            top_imports = aggregate_top_imports(file_imports)

        in_makefile = name in makefile_refs
        in_ci = name in ci_refs
        has_any_test = has_tests and test_file_count > 0

        own = ownership.get(name, {})
        sensitivity = own.get("sensitivity", "unknown")
        migration_wave = own.get("migration_wave", "unknown")

        high_sensitivity = sensitivity == "high"

        has_packaging = any([has_pyproject, has_requirements, has_setup_py, has_setup_cfg])

        entry = {
            "name": name,
            "runtime": runtime,
            "has_src": has_src,
            "has_tests": has_tests,
            "has_any_test": has_any_test,
            "test_file_count": test_file_count,
            "py_file_count": py_file_count,
            "has_pyproject_toml": has_pyproject,
            "has_requirements_txt": has_requirements,
            "has_setup_py": has_setup_py,
            "has_setup_cfg": has_setup_cfg,
            "has_any_packaging": has_packaging,
            "in_makefile": in_makefile,
            "in_ci": in_ci,
            "sensitivity": sensitivity,
            "high_sensitivity": high_sensitivity,
            "migration_wave": migration_wave,
            "code_owner": own.get("code_owner", "TBD"),
            "runtime_owner": own.get("runtime_owner", "TBD"),
            "top_imports": top_imports,
            "packaging_gap": bool(not has_packaging and is_python),
            "test_gap": bool(not has_any_test and is_python),
        }

        results.append(entry)

    return results


def compute_summary(inv: list[dict]) -> dict:
    total = len(inv)
    python_svcs = [s for s in inv if s["runtime"] == "python"]
    node_svcs = [s for s in inv if s["runtime"] == "node"]
    no_packaging = [s["name"] for s in python_svcs if s["packaging_gap"]]
    no_tests = [s["name"] for s in python_svcs if s["test_gap"]]
    high_sens_no_packaging = [
        s["name"] for s in python_svcs if s["high_sensitivity"] and s["packaging_gap"]
    ]
    high_sens_no_tests = [
        s["name"] for s in python_svcs if s["high_sensitivity"] and s["test_gap"]
    ]
    in_ci = [s["name"] for s in inv if s["in_ci"]]
    not_in_ci = [s["name"] for s in inv if not s["in_ci"]]

    return {
        "total_services": total,
        "python_services": len(python_svcs),
        "node_services": len(node_svcs),
        "python_services_with_packaging": len([s for s in python_svcs if s["has_any_packaging"]]),
        "python_services_without_packaging": len(no_packaging),
        "python_services_without_packaging_list": no_packaging,
        "high_sensitivity_without_packaging": high_sens_no_packaging,
        "python_services_without_tests": no_tests,
        "high_sensitivity_without_tests": high_sens_no_tests,
        "services_in_ci": len(in_ci),
        "services_not_in_ci": not_in_ci,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory Python service packaging status")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root")
    parser.add_argument("--output", type=Path, help="Path to write JSON output")
    parser.add_argument("--summary-only", action="store_true", help="Print summary and exit")
    parser.add_argument("--fail-on-gap", action="store_true",
                        help="Exit 1 if any Python service lacks packaging")
    parser.add_argument("--fail-on-high-sensitivity-gap", action="store_true",
                        help="Exit 1 if any high-sensitivity Python service lacks packaging")
    args = parser.parse_args()

    root = args.root.resolve()
    if not (root / SERVICE_DIR).is_dir():
        print(f"ERROR: {SERVICE_DIR}/ not found under {root}", file=sys.stderr)
        sys.exit(2)

    inv = inventory(root)
    summary = compute_summary(inv)
    report = {
        "schema_version": 1,
        "root": str(root),
        "summary": summary,
        "services": inv,
    }

    json_text = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json_text, encoding="utf-8")
        print(f"Inventory written to {args.output}")
    else:
        print(json_text)

    if args.summary_only:
        return

    if args.fail_on_gap:
        gaps = summary["python_services_without_packaging_list"]
        if gaps:
            print(f"FAIL: {len(gaps)} Python service(s) lack packaging: {gaps}", file=sys.stderr)
            sys.exit(1)

    if args.fail_on_high_sensitivity_gap:
        gaps = summary["high_sensitivity_without_packaging"]
        if gaps:
            print(f"FAIL: {len(gaps)} high-sensitivity service(s) lack packaging: {gaps}",
                  file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
