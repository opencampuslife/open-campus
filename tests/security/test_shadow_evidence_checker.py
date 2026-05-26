from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_SRC = ROOT / "tools"
sys.path.insert(0, str(TOOLS_SRC))

import check_shadow_evidence  # noqa: E402


class ShadowEvidenceCheckerTest(unittest.TestCase):
    def test_default_mode_allows_skipped_local_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report_dir = root / "reports" / "shadow"
            report_dir.mkdir(parents=True, exist_ok=True)
            _write_latest(report_dir / "latest.json", chat_parity="skipped", admin_parity="skipped")
            _write_mirror(report_dir / "mirror-latest.json", mode="dry_run", skipped_cases=2, executed_cases=0)

            latest = check_shadow_evidence.load_json(report_dir / "latest.json")
            mirror = check_shadow_evidence.load_json(report_dir / "mirror-latest.json")
            errors: list[str] = []
            check_shadow_evidence.check_forbidden_fields(latest, "latest.json", errors)
            check_shadow_evidence.check_forbidden_fields(mirror, "mirror-latest.json", errors)
            errors.extend(check_shadow_evidence.validate_dry_run_report(latest, strict=False, allow_legacy_usage_waiver=False))
            errors.extend(check_shadow_evidence.validate_mirror_report(mirror, strict=False))

            self.assertEqual(errors, [])

    def test_strict_mode_requires_live_passed_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report_dir = root / "reports" / "shadow"
            report_dir.mkdir(parents=True, exist_ok=True)
            _write_latest(report_dir / "latest.json", chat_parity="skipped", admin_parity="passed")
            _write_mirror(report_dir / "mirror-latest.json", mode="dry_run", skipped_cases=1, executed_cases=0)

            latest = check_shadow_evidence.load_json(report_dir / "latest.json")
            mirror = check_shadow_evidence.load_json(report_dir / "mirror-latest.json")
            errors = check_shadow_evidence.validate_dry_run_report(latest, strict=True, allow_legacy_usage_waiver=False)
            errors.extend(check_shadow_evidence.validate_mirror_report(mirror, strict=True))

            self.assertTrue(any("chat_parity=passed" in error for error in errors))
            self.assertTrue(any("mode=live" in error for error in errors))

    def test_forbidden_raw_body_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report_dir = root / "reports" / "shadow"
            report_dir.mkdir(parents=True, exist_ok=True)
            _write_latest(report_dir / "latest.json", chat_parity="passed", admin_parity="passed")
            mirror_path = report_dir / "mirror-latest.json"
            mirror = _mirror_report(mode="live", skipped_cases=0, executed_cases=1)
            mirror["cases"][0]["body"] = "secret"
            mirror_path.write_text(json.dumps(mirror, indent=2) + "\n", encoding="utf-8")

            mirror = check_shadow_evidence.load_json(mirror_path)
            errors: list[str] = []
            check_shadow_evidence.check_forbidden_fields(mirror, "mirror-latest.json", errors)

            self.assertTrue(any("forbidden report field body" in error for error in errors))


def _write_latest(path: Path, chat_parity: str, admin_parity: str) -> None:
    payload = {
        "summary": {
            "health_ok": True,
            "route_count": 115,
            "legacy_gaps": 0,
            "deprecated_aliases": 5,
            "chat_parity": chat_parity,
            "admin_post_parity": admin_parity,
            "legacy_get_usage_events": 0,
        },
        "latency": {
            "chat_warn_count": 0,
            "admin_warn_count": 0,
        },
        "details": {
            "chat_passed": 0,
            "chat_failed": 0,
            "chat_skipped": 1 if chat_parity == "skipped" else 0,
            "admin_passed": 1 if admin_parity == "passed" else 0,
            "admin_failed": 0,
            "admin_skipped": 1 if admin_parity == "skipped" else 0,
        },
        "parity_cases": {
            "chat": [],
            "admin": [],
        },
        "diffs": [],
        "inventory": {
            "state-changing GET gaps": "0",
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _mirror_report(mode: str, skipped_cases: int, executed_cases: int) -> dict:
    return {
        "generated_at": "2026-05-27T00:00:00Z",
        "mode": mode,
        "summary": {
            "total_cases": 1,
            "executed_cases": executed_cases,
            "skipped_cases": skipped_cases,
            "drifted_cases": 0,
        },
        "cases": [
            {
                "name": "chat_basic",
                "method": "POST",
                "path": "/api/gaokao/chat",
                "comparison_status": "passed" if mode == "live" else "skipped",
                "legacy_status": 200 if mode == "live" else None,
                "shadow_status": 200 if mode == "live" else None,
                "legacy_latency_ms": 100 if mode == "live" else None,
                "shadow_latency_ms": 110 if mode == "live" else None,
                "latency_ratio": 1.1 if mode == "live" else None,
                "diff_category": "none" if mode == "live" else "skipped",
                "legacy_body_summary": "[redacted len=15 sha256=0123456789abcdef]" if mode == "live" else None,
                "shadow_body_summary": "[redacted len=15 sha256=0123456789abcdef]" if mode == "live" else None,
            }
        ],
    }


def _write_mirror(path: Path, mode: str, skipped_cases: int, executed_cases: int) -> None:
    path.write_text(json.dumps(_mirror_report(mode, skipped_cases, executed_cases), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
