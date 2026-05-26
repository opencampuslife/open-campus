from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
SCRIPTS = ROOT / "scripts"
EXAMPLE_YAML = (
    ROOT / "deploy" / "staging" / "ingress" / "go-gateway-shadow.percentage-canary.example.yaml"
)
POLICY_YAML = ROOT / "configs" / "cutover_policy.yaml"


class StagingPercentageCanaryEvidenceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = Path(tempfile.mkdtemp())
        self.output_config = self.tmpdir / "staging-1pct-canary.yaml"
        self.output_report = self.tmpdir / "percentage-canary-1pct-latest.json"

    def test_render_config_creates_valid_yaml(self) -> None:
        """render tool should create valid YAML with current_weight=1."""
        result = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "render_staging_percentage_canary_config.py"),
                "--source", str(EXAMPLE_YAML),
                "--percent", "1",
                "--output", str(self.output_config),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertTrue(self.output_config.is_file())

        import yaml
        config = yaml.safe_load(self.output_config.read_text())
        self.assertEqual(config["canary"]["current_weight"], 1)
        self.assertEqual(config["canary"]["type"], "percentage")

    def test_render_config_rejects_bad_source_weight(self) -> None:
        """render tool should reject source with current_weight != 0."""
        bad_source = self.tmpdir / "bad-source.yaml"
        import yaml
        bad_config = yaml.safe_load(EXAMPLE_YAML.read_text())
        bad_config["canary"]["current_weight"] = 5
        bad_source.write_text(yaml.safe_dump(bad_config))

        result = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "render_staging_percentage_canary_config.py"),
                "--source", str(bad_source),
                "--percent", "1",
                "--output", str(self.output_config),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_render_config_requires_stages_whitelist_percent(self) -> None:
        """render tool only allows percent from stages whitelist."""
        for pct in [1, 5, 25, 50, 100]:
            result = subprocess.run(
                [
                    sys.executable,
                    str(TOOLS / "render_staging_percentage_canary_config.py"),
                    "--source", str(EXAMPLE_YAML),
                    "--percent", str(pct),
                    "--output", str(self.tmpdir / f"test-{pct}.yaml"),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"pct={pct} failed: {result.stderr}")

    def test_collect_evidence_skipped_without_env(self) -> None:
        """Without STAGING_ENV_CONFIRMED=true, status should be skipped."""
        subprocess.run(
            [
                sys.executable,
                str(TOOLS / "render_staging_percentage_canary_config.py"),
                "--source", str(EXAMPLE_YAML),
                "--percent", "1",
                "--output", str(self.output_config),
            ],
            check=True,
        )

        env = os.environ.copy()
        env.pop("STAGING_ENV_CONFIRMED", None)

        result = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "collect_staging_percentage_canary_result.py"),
                "--config", str(self.output_config),
                "--policy", str(POLICY_YAML),
                "--percent", "1",
                "--report", str(self.output_report),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, 0, f"stderr: {result.stderr}")
        self.assertTrue(self.output_report.is_file())

        report = json.loads(self.output_report.read_text())
        self.assertEqual(report["status"], "skipped")
        self.assertEqual(report["percent"], 1)
        self.assertFalse(report["summary"]["staging_env_confirmed"])

    def test_collect_evidence_rejects_wrong_weight(self) -> None:
        """collect tool should reject config with current_weight != requested percent."""
        import yaml
        wrong_config = yaml.safe_load(EXAMPLE_YAML.read_text())
        wrong_config["canary"]["current_weight"] = 5
        self.output_config.write_text(yaml.safe_dump(wrong_config))

        result = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "collect_staging_percentage_canary_result.py"),
                "--config", str(self.output_config),
                "--policy", str(POLICY_YAML),
                "--percent", "1",
                "--report", str(self.output_report),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)

    def test_collect_evidence_privacy_fields(self) -> None:
        """Evidence report should have privacy fields set correctly."""
        subprocess.run(
            [
                sys.executable,
                str(TOOLS / "render_staging_percentage_canary_config.py"),
                "--source", str(EXAMPLE_YAML),
                "--percent", "1",
                "--output", str(self.output_config),
            ],
            check=True,
        )

        env = os.environ.copy()
        env.pop("STAGING_ENV_CONFIRMED", None)

        subprocess.run(
            [
                sys.executable,
                str(TOOLS / "collect_staging_percentage_canary_result.py"),
                "--config", str(self.output_config),
                "--policy", str(POLICY_YAML),
                "--percent", "1",
                "--report", str(self.output_report),
            ],
            check=True,
            env=env,
        )

        report = json.loads(self.output_report.read_text())
        self.assertFalse(report["privacy"]["raw_payload_included"])
        self.assertFalse(report["privacy"]["contains_pii"])

    def test_script_help_flags(self) -> None:
        """Tools should respond to --help without error."""
        for tool in [
            "render_staging_percentage_canary_config.py",
            "collect_staging_percentage_canary_result.py",
        ]:
            result = subprocess.run(
                [sys.executable, str(TOOLS / tool), "--help"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"{tool}: {result.stderr}")

    def test_script_rejects_bad_percent(self) -> None:
        """Render tool should reject invalid percent values."""
        result = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "render_staging_percentage_canary_config.py"),
                "--source", str(EXAMPLE_YAML),
                "--percent", "99",
                "--output", str(self.output_config),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
