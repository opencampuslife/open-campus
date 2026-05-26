from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_SRC = ROOT / "tools"
sys.path.insert(0, str(TOOLS_SRC))

import check_staging_ingress_config as checker


class StagingIngressConfigTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.policy_path = self.tmpdir / "cutover_policy.yaml"
        self.config_path = self.tmpdir / "ingress.yaml"

        policy = {
            "version": 1,
            "mode": "design_only",
            "allowed_cutover_routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "phase": "production_canary_public", "max_initial_percent": 1},
                {"method": "POST", "path": "/api/admin/staging/docs/{doc_id}/validate", "phase": "production_canary_admin", "max_initial_percent": 1},
            ],
            "blocked_routes": [
                {"method": "GET", "path_pattern": "/api/admin/**", "reason": "deprecated"},
                {"method": "*", "path_pattern": "/api/admin/**", "reason": "forbidden", "allow_if_explicitly_listed": True},
            ],
            "rollback_triggers": {},
        }
        self.policy_path.write_text(json.dumps(policy), encoding="utf-8")

    def _write_config(self, config: dict) -> None:
        self.config_path.write_text(json.dumps(config), encoding="utf-8")

    def _run_check(self, config: dict, allow_enabled=False, allow_weight=False, allow_header_canary=False, allow_percentage_canary=False) -> int:
        self._write_config(config)
        old_argv = sys.argv[:]
        sys.argv = [
            "check_staging_ingress_config.py",
            "--config", str(self.config_path),
            "--policy", str(self.policy_path),
        ]
        if allow_enabled:
            sys.argv.append("--allow-enabled")
        if allow_weight:
            sys.argv.append("--allow-weight")
        if allow_header_canary:
            sys.argv.append("--allow-header-canary")
        if allow_percentage_canary:
            sys.argv.append("--allow-percentage-canary")
        try:
            return checker.main()
        finally:
            sys.argv = old_argv

    # ── Original tests ──

    def test_valid_config_passes(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": False,
            "default_weight": 0,
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "route_to": "go_gateway", "enabled": False, "weight": 0},
            ],
        }
        self.assertEqual(self._run_check(config), 0)

    def test_mode_must_be_staging_only(self) -> None:
        config = {"mode": "production", "enabled": False, "default_weight": 0, "upstreams": {}, "routes": []}
        self.assertNotEqual(self._run_check(config), 0)

    def test_enabled_must_be_false(self) -> None:
        config = {"mode": "staging_only", "enabled": True, "default_weight": 0, "upstreams": {}, "routes": []}
        self.assertNotEqual(self._run_check(config), 0)
        self.assertEqual(self._run_check(config, allow_enabled=True), 0)

    def test_default_weight_must_be_zero(self) -> None:
        config = {"mode": "staging_only", "enabled": False, "default_weight": 10, "upstreams": {}, "routes": []}
        self.assertNotEqual(self._run_check(config), 0)

    def test_route_not_in_policy_is_rejected(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": False,
            "default_weight": 0,
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/unauthorized/route", "route_to": "go_gateway", "enabled": False, "weight": 0},
            ],
        }
        self.assertNotEqual(self._run_check(config), 0)

    def test_wildcard_path_rejected(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": False,
            "default_weight": 0,
            "upstreams": {},
            "routes": [
                {"method": "POST", "path": "/api/admin/*", "route_to": "go", "enabled": False, "weight": 0},
            ],
        }
        self.assertNotEqual(self._run_check(config), 0)

    def test_get_admin_route_rejected(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": False,
            "default_weight": 0,
            "upstreams": {},
            "routes": [
                {"method": "GET", "path": "/api/admin/staging/docs/d1/validate", "route_to": "go", "enabled": False, "weight": 0},
            ],
        }
        self.assertNotEqual(self._run_check(config), 0)

    def test_weight_must_be_zero(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": False,
            "default_weight": 0,
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "route_to": "go_gateway", "enabled": False, "weight": 50},
            ],
        }
        self.assertNotEqual(self._run_check(config), 0)
        self.assertEqual(self._run_check(config, allow_weight=True), 0)

    # ── Header canary tests ──

    def test_header_canary_default_config_fails_normal_check(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Gaokao-Gateway-Canary", "value": "go"},
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "route_to": "go_gateway", "enabled": True, "weight": 0,
                 "canary": {"type": "header", "header": "X-Gaokao-Gateway-Canary", "value": "go"}},
            ],
        }
        result = self._run_check(config)
        self.assertNotEqual(result, 0)

    def test_header_canary_passes_with_allow_header_canary(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Gaokao-Gateway-Canary", "value": "go"},
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "route_to": "go_gateway", "enabled": True, "weight": 0,
                 "canary": {"type": "header", "header": "X-Gaokao-Gateway-Canary", "value": "go"}},
            ],
        }
        self.assertEqual(self._run_check(config, allow_header_canary=True), 0)

    def test_header_canary_wrong_header_name_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Wrong-Header", "value": "go"},
            "upstreams": {},
            "routes": [],
        }
        self.assertNotEqual(self._run_check(config, allow_header_canary=True), 0)

    def test_header_canary_wrong_value_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Gaokao-Gateway-Canary", "value": "python"},
            "upstreams": {},
            "routes": [],
        }
        self.assertNotEqual(self._run_check(config, allow_header_canary=True), 0)

    def test_header_canary_weight_still_must_be_zero(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Gaokao-Gateway-Canary", "value": "go"},
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "route_to": "go_gateway", "enabled": True, "weight": 10,
                 "canary": {"type": "header", "header": "X-Gaokao-Gateway-Canary", "value": "go"}},
            ],
        }
        self.assertNotEqual(self._run_check(config, allow_header_canary=True), 0)
        self.assertEqual(self._run_check(config, allow_header_canary=True, allow_weight=True), 0)

    def test_header_canary_wildcard_route_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Gaokao-Gateway-Canary", "value": "go"},
            "upstreams": {},
            "routes": [
                {"method": "GET", "path": "/api/admin/**", "route_to": "go_gateway", "enabled": True, "weight": 0,
                 "canary": {"type": "header", "header": "X-Gaokao-Gateway-Canary", "value": "go"}},
            ],
        }
        self.assertNotEqual(self._run_check(config, allow_header_canary=True), 0)

    def test_header_canary_deprecated_get_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Gaokao-Gateway-Canary", "value": "go"},
            "upstreams": {},
            "routes": [
                {"method": "GET", "path": "/api/admin/staging/docs/d1/validate", "route_to": "go_gateway", "enabled": True, "weight": 0,
                 "canary": {"type": "header", "header": "X-Gaokao-Gateway-Canary", "value": "go"}},
            ],
        }
        self.assertNotEqual(self._run_check(config, allow_header_canary=True), 0)

    def test_header_canary_production_host_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "header", "enabled": True, "header": "X-Gaokao-Gateway-Canary", "value": "go"},
            "upstreams": {"go_gateway": {"url": "http://prod-gateway:8788"}},
            "routes": [],
        }
        self.assertNotEqual(self._run_check(config, allow_header_canary=True), 0)

    def test_real_example_config_passes(self) -> None:
        example = ROOT / "deploy" / "staging" / "ingress" / "go-gateway-shadow.example.yaml"
        if not example.is_file():
            self.skipTest(f"Example config not found: {example}")
        old_argv = sys.argv[:]
        sys.argv = [
            "check_staging_ingress_config.py",
            "--config", str(example),
            "--policy", str(ROOT / "configs" / "cutover_policy.yaml"),
        ]
        try:
            result = checker.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(result, 0, "Default example config should pass")

    def test_header_canary_example_config_passes_with_flag(self) -> None:
        example = ROOT / "deploy" / "staging" / "ingress" / "go-gateway-shadow.header-canary.example.yaml"
        if not example.is_file():
            self.skipTest(f"Header canary example config not found: {example}")
        old_argv = sys.argv[:]
        sys.argv = [
            "check_staging_ingress_config.py",
            "--config", str(example),
            "--policy", str(ROOT / "configs" / "cutover_policy.yaml"),
            "--allow-header-canary",
        ]
        try:
            result = checker.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(result, 0, "Header canary example config should pass with --allow-header-canary")

    def test_header_canary_example_fails_without_flag(self) -> None:
        example = ROOT / "deploy" / "staging" / "ingress" / "go-gateway-shadow.header-canary.example.yaml"
        if not example.is_file():
            self.skipTest(f"Header canary example config not found: {example}")
        old_argv = sys.argv[:]
        sys.argv = [
            "check_staging_ingress_config.py",
            "--config", str(example),
            "--policy", str(ROOT / "configs" / "cutover_policy.yaml"),
        ]
        try:
            result = checker.main()
        finally:
            sys.argv = old_argv
        self.assertNotEqual(result, 0, "Header canary example config should fail without --allow-header-canary")

    # ── Percentage canary tests (PR-6D) ──

    def test_percentage_canary_default_config_fails_normal_check(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "percentage", "enabled": True, "current_weight": 0, "stages": [1, 5, 25]},
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [],
        }
        result = self._run_check(config)
        self.assertNotEqual(result, 0, "percentage canary config should fail normal check")

    def test_percentage_canary_passes_with_allow_flag(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "percentage", "enabled": True, "current_weight": 0, "stages": [1, 5, 25]},
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "route_to": "go_gateway", "enabled": True, "weight": 0,
                 "canary": {"type": "percentage", "current_weight": 0}},
            ],
        }
        self.assertEqual(self._run_check(config, allow_percentage_canary=True), 0)

    def test_percentage_current_weight_gt0_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "percentage", "enabled": True, "current_weight": 5, "stages": [1, 5, 25]},
            "upstreams": {},
            "routes": [],
        }
        self.assertNotEqual(self._run_check(config, allow_percentage_canary=True), 0)

    def test_percentage_route_weight_gt0_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "percentage", "enabled": True, "current_weight": 0, "stages": [1, 5, 25]},
            "upstreams": {"go_gateway": {"url": "http://go:8788"}},
            "routes": [
                {"method": "POST", "path": "/api/gaokao/chat", "route_to": "go_gateway", "enabled": True, "weight": 10,
                 "canary": {"type": "percentage", "current_weight": 10}},
            ],
        }
        self.assertNotEqual(self._run_check(config, allow_percentage_canary=True), 0)
        self.assertEqual(self._run_check(config, allow_percentage_canary=True, allow_weight=True), 0)

    def test_percentage_invalid_stages_fail(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "percentage", "enabled": True, "current_weight": 0, "stages": [5, 1, 25]},  # not increasing
            "upstreams": {},
            "routes": [],
        }
        self.assertNotEqual(self._run_check(config, allow_percentage_canary=True), 0)

    def test_percentage_invalid_stage_value_fails(self) -> None:
        config = {
            "mode": "staging_only",
            "enabled": True,
            "default_weight": 0,
            "canary": {"type": "percentage", "enabled": True, "current_weight": 0, "stages": [1, 5, 99]},
            "upstreams": {},
            "routes": [],
        }
        self.assertNotEqual(self._run_check(config, allow_percentage_canary=True), 0)

    def test_percentage_example_config_passes_with_flag(self) -> None:
        example = ROOT / "deploy" / "staging" / "ingress" / "go-gateway-shadow.percentage-canary.example.yaml"
        if not example.is_file():
            self.skipTest(f"Percentage canary example config not found: {example}")
        old_argv = sys.argv[:]
        sys.argv = [
            "check_staging_ingress_config.py",
            "--config", str(example),
            "--policy", str(ROOT / "configs" / "cutover_policy.yaml"),
            "--allow-percentage-canary",
        ]
        try:
            result = checker.main()
        finally:
            sys.argv = old_argv
        self.assertEqual(result, 0, "Percentage canary example config should pass with --allow-percentage-canary")

    def test_percentage_example_fails_without_flag(self) -> None:
        example = ROOT / "deploy" / "staging" / "ingress" / "go-gateway-shadow.percentage-canary.example.yaml"
        if not example.is_file():
            self.skipTest(f"Percentage canary example config not found: {example}")
        old_argv = sys.argv[:]
        sys.argv = [
            "check_staging_ingress_config.py",
            "--config", str(example),
            "--policy", str(ROOT / "configs" / "cutover_policy.yaml"),
        ]
        try:
            result = checker.main()
        finally:
            sys.argv = old_argv
        self.assertNotEqual(result, 0, "Percentage canary example config should fail without --allow-percentage-canary")


if __name__ == "__main__":
    unittest.main()
