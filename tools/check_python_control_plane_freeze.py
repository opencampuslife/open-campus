from __future__ import annotations

import argparse
import ast
import json
from collections import Counter
from pathlib import Path

from check_route_contract import check_route_contract


OPERATIONS = {"append", "extend", "insert"}


def production_sys_path_calls(root: Path) -> Counter[tuple[str, str, str]]:
    findings: Counter[tuple[str, str, str]] = Counter()
    for path in sorted((root / "services").glob("*/src/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in OPERATIONS:
                continue
            target = node.func.value
            if not isinstance(target, ast.Attribute) or not isinstance(target.value, ast.Name):
                continue
            if target.value.id != "sys" or target.attr != "path":
                continue
            relative_path = str(path.relative_to(root))
            findings[(relative_path, node.func.attr, ast.unparse(node))] += 1
    return findings


def load_allowlist(root: Path) -> Counter[tuple[str, str, str]]:
    payload = json.loads(
        (root / "contracts" / "python_control_plane_allowlist.json").read_text(encoding="utf-8")
    )
    return Counter(
        (entry["path"], entry["operation"], entry["expression"])
        for entry in payload.get("entries", [])
    )


def check_python_boundary(root: Path) -> list[str]:
    errors = check_route_contract(root)
    allowed = load_allowlist(root)
    actual = production_sys_path_calls(root)
    for finding, count in sorted((actual - allowed).items()):
        path, operation, expression = finding
        errors.append(
            f"new production sys.path.{operation} debt in {path} ({count}x): {expression}"
        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    errors = check_python_boundary(args.root)
    if errors:
        for error in errors:
            print(f"PYTHON CONTROL PLANE FREEZE FAIL: {error}")
        return 1
    print("python control-plane freeze checks: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
