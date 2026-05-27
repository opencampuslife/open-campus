#!/usr/bin/env python3
from __future__ import annotations

import runpy
from pathlib import Path


if __name__ == "__main__":
    # Compatibility wrapper. The canonical implementation remains
    # tools/ci_policy_check.py so existing Makefile targets keep working.
    target = Path(__file__).resolve().with_name("ci_policy_check.py")
    runpy.run_path(str(target), run_name="__main__")
