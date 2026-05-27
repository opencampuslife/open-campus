#!/usr/bin/env python3
"""
Service ownership contract validator.

Ensures every services/* directory has an entry in the ownership contract,
required owners are non-TBD, high-sensitivity services have reviewers,
and README service count matches reality.

Usage:
  python tools/check_service_ownership.py --root .
  python tools/check_service_ownership.py --root . --allow-tbd
"""

import json
import os
import re
import sys

CONTRACT = "contracts/service_ownership.json"
NON_SERVICE_DIRS = {"uploads"}
HIGH_SENSITIVITY = "high"


def load_contract(root):
    path = os.path.join(root, CONTRACT)
    if not os.path.exists(path):
        print(f"[FAIL] {CONTRACT}: file missing")
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        print(f"[FAIL] {CONTRACT}: invalid schema_version (expected 1)")
        sys.exit(1)
    return data


def list_services(root):
    services_dir = os.path.join(root, "services")
    if not os.path.isdir(services_dir):
        return []
    return sorted([
        d for d in os.listdir(services_dir)
        if os.path.isdir(os.path.join(services_dir, d)) and d not in NON_SERVICE_DIRS
    ])


def check(root, allow_tbd=False):
    contract = load_contract(root)
    contract_services = {s["name"] for s in contract["services"]}
    actual_services = list_services(root)
    exit_code = 0

    for svc in actual_services:
        if svc not in contract_services:
            print(f"[FAIL] services/{svc}: no entry in {CONTRACT}")
            exit_code = 1

    for svc in contract_services:
        if svc not in actual_services:
            print(f"[FAIL] services/{svc}: in {CONTRACT} but directory not found")
            exit_code = 1

    if exit_code != 0:
        return exit_code

    for entry in contract["services"]:
        name = entry["name"]
        code_owner = entry.get("code_owner", "TBD")

        if code_owner == "TBD" and not allow_tbd:
            print(f"[FAIL] services/{name}: code_owner is TBD")
            exit_code = 1

        if entry.get("sensitivity") == HIGH_SENSITIVITY and not allow_tbd:
            sec = entry.get("security_reviewer")
            data = entry.get("data_reviewer")
            if not sec and not data:
                print(f"[FAIL] services/{name}: high-sensitivity requires security_reviewer or data_reviewer")
                exit_code = 1

    readme_count = read_readme_service_count(root)
    actual_count = len(actual_services)
    if readme_count is not None and readme_count != actual_count:
        print(f"[FAIL] README.md says '{readme_count} services' but services/ has {actual_count}")
        exit_code = 1

    print(f"[INFO] discovered {len(actual_services)} services: {','.join(actual_services)}")
    if NON_SERVICE_DIRS:
        print(f"[INFO] excluded non-service dirs: {','.join(NON_SERVICE_DIRS)}")

    if exit_code == 0:
        print(f"[PASS] service ownership OK: {len(actual_services)} services matched, no gaps")
        if allow_tbd:
            print("[WARN] --allow-tbd enabled; TBD owners not enforced. Remove this flag once owners are assigned.")

    return exit_code


def read_readme_service_count(root):
    path = os.path.join(root, "README.md")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        content = f.read()
    m = re.search(r"Python capability services \((\d+) services", content)
    if m:
        return int(m.group(1))
    return None


def main():
    import argparse
    p = argparse.ArgumentParser(description="Service ownership contract validator")
    p.add_argument("--root", default=".", help="Repo root directory")
    p.add_argument("--allow-tbd", action="store_true",
                   help="Allow TBD owners (transitional; remove once owners are assigned)")
    args = p.parse_args()
    sys.exit(check(os.path.abspath(args.root), allow_tbd=args.allow_tbd))


if __name__ == "__main__":
    main()
