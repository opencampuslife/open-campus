from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_SRC = ROOT / "tools"
sys.path.insert(0, str(TOOLS_SRC))

import check_observability_contract as checker


class ObservabilityContractTest(unittest.TestCase):
    def test_contract_shape_valid(self) -> None:
        contract_path = ROOT / "configs" / "observability_contract.yaml"
        contract = checker.load_json_yaml(contract_path)
        errors = checker.validate_contract_shape(contract)
        self.assertEqual(errors, [])

    def test_required_fields_present_in_request_fixture(self) -> None:
        contract_path = ROOT / "configs" / "observability_contract.yaml"
        contract = checker.load_json_yaml(contract_path)
        fixture_path = ROOT / "tests" / "fixtures" / "observability" / "go_gateway_request_log.json"
        data = checker.load_json_yaml(fixture_path)
        errors: list[str] = []
        for idx, entry in enumerate(data):
            errors.extend(checker.check_log_fixture(entry, contract, f"go_gateway_request_log.json[{idx}]"))
        self.assertEqual(errors, [])

    def test_admin_fields_present_for_admin_routes(self) -> None:
        contract_path = ROOT / "configs" / "observability_contract.yaml"
        contract = checker.load_json_yaml(contract_path)
        fixture_path = ROOT / "tests" / "fixtures" / "observability" / "go_gateway_request_log.json"
        data = checker.load_json_yaml(fixture_path)
        admin_entries = [e for e in data if e.get("surface") == "admin"]
        self.assertTrue(len(admin_entries) > 0, "need at least one admin fixture")
        for entry in admin_entries:
            admin_fields = contract.get("required_admin_fields", [])
            for field in admin_fields:
                self.assertIn(field, entry, f"admin fixture missing field {field!r}")

    def test_forbidden_fields_absent_in_fixtures(self) -> None:
        contract_path = ROOT / "configs" / "observability_contract.yaml"
        contract = checker.load_json_yaml(contract_path)
        forbidden = set(contract.get("forbidden_fields", []))
        fixtures_dir = ROOT / "tests" / "fixtures" / "observability"
        for fixture_path in fixtures_dir.iterdir():
            if not fixture_path.suffix == ".json":
                continue
            data = checker.load_json_yaml(fixture_path)
            for entry in data if isinstance(data, list) else [data]:
                log_keys = set(entry.keys())
                overlap = log_keys & forbidden
                self.assertEqual(overlap, set(), f"{fixture_path.name} contains forbidden fields: {overlap}")

    def test_error_codes_are_allowed(self) -> None:
        contract_path = ROOT / "configs" / "observability_contract.yaml"
        contract = checker.load_json_yaml(contract_path)
        allowed = set(contract.get("error_codes", []))
        fixtures_dir = ROOT / "tests" / "fixtures" / "observability"
        for fixture_path in fixtures_dir.iterdir():
            if not fixture_path.suffix == ".json":
                continue
            data = checker.load_json_yaml(fixture_path)
            for entry in data if isinstance(data, list) else [data]:
                code = entry.get("error_code")
                if code and code not in allowed:
                    self.fail(f"{fixture_path.name}: unknown error_code {code!r}")

    def test_metrics_have_correct_labels(self) -> None:
        contract_path = ROOT / "configs" / "observability_contract.yaml"
        contract = checker.load_json_yaml(contract_path)
        allowed = {m["name"]: set(m["labels"]) for m in contract.get("metrics", [])}
        forbidden_label_names = set(contract.get("forbidden_metric_labels", []))

        for metric_name, labels in allowed.items():
            self.assertNotIn("raw_user_id", labels, f"metric {metric_name!r} has high-cardinality label raw_user_id")
            self.assertNotIn("request_id", labels, f"metric {metric_name!r} has high-cardinality label request_id")

        for label in forbidden_label_names:
            for metric_name, labels in allowed.items():
                self.assertNotIn(label, labels, f"metric {metric_name!r} has forbidden label {label!r}")

    def test_checker_passes_on_valid_fixtures(self) -> None:
        contract_path = ROOT / "configs" / "observability_contract.yaml"
        fixtures_dir = ROOT / "tests" / "fixtures" / "observability"
        contract = checker.load_json_yaml(contract_path)
        errors = checker.check_fixtures(fixtures_dir, contract)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
