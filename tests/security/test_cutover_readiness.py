from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_SRC = ROOT / "tools"
sys.path.insert(0, str(TOOLS_SRC))

import check_cutover_readiness  # noqa: E402


class CutoverReadinessTest(unittest.TestCase):
    def test_default_policy_matches_route_contract(self) -> None:
        policy = check_cutover_readiness.load_json_yaml(ROOT / "configs" / "cutover_policy.yaml")
        routes = check_cutover_readiness.load_json_yaml(ROOT / "contracts" / "routes.yaml")

        errors: list[str] = []
        errors.extend(check_cutover_readiness.validate_policy_shape(policy))
        errors.extend(check_cutover_readiness.validate_allowed_routes(policy, routes))
        errors.extend(check_cutover_readiness.validate_blocked_routes(policy))
        errors.extend(check_cutover_readiness.validate_blocked_vs_allowed(policy))
        errors.extend(check_cutover_readiness.validate_rollback_triggers(policy))

        self.assertEqual(errors, [])

    def test_deprecated_get_alias_is_rejected_from_allowlist(self) -> None:
        policy = check_cutover_readiness.load_json_yaml(ROOT / "configs" / "cutover_policy.yaml")
        routes = check_cutover_readiness.load_json_yaml(ROOT / "contracts" / "routes.yaml")
        broken = json.loads(json.dumps(policy))
        broken["allowed_cutover_routes"].append(
            {
                "method": "GET",
                "path": "/api/admin/staging/docs/{doc_id}/validate",
                "phase": "production_canary_admin",
                "max_initial_percent": 1,
            }
        )

        errors = check_cutover_readiness.validate_allowed_routes(broken, routes)

        self.assertTrue(any("cannot include legacy/deprecated route" in error for error in errors))

    def test_admin_wildcard_allowlist_is_rejected(self) -> None:
        policy = check_cutover_readiness.load_json_yaml(ROOT / "configs" / "cutover_policy.yaml")
        routes = check_cutover_readiness.load_json_yaml(ROOT / "contracts" / "routes.yaml")
        broken = json.loads(json.dumps(policy))
        broken["allowed_cutover_routes"].append(
            {
                "method": "POST",
                "path": "/api/admin/**",
                "phase": "production_canary_admin",
                "max_initial_percent": 1,
            }
        )

        errors = check_cutover_readiness.validate_allowed_routes(broken, routes)

        self.assertTrue(any("must not use wildcard path" in error for error in errors))

    def test_strict_requires_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            policy_path = Path(tmp_dir) / "policy.yaml"
            routes_path = Path(tmp_dir) / "routes.yaml"
            policy_path.write_text((ROOT / "configs" / "cutover_policy.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            routes_path.write_text((ROOT / "contracts" / "routes.yaml").read_text(encoding="utf-8"), encoding="utf-8")
            args = type(
                "Args",
                (),
                {
                    "shadow_report": None,
                    "mirror_report": None,
                    "allow_legacy_usage_waiver": False,
                },
            )()

            errors = check_cutover_readiness.validate_strict_evidence(args)

            self.assertIn("strict mode requires --shadow-report", errors)
            self.assertIn("strict mode requires --mirror-report", errors)


if __name__ == "__main__":
    unittest.main()
