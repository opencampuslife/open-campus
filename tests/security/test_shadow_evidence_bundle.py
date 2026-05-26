from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS_SRC = ROOT / "tools"
sys.path.insert(0, str(TOOLS_SRC))

import build_shadow_evidence_bundle as builder


class ShadowEvidenceBundleTest(unittest.TestCase):
    def _make_args(self, extra_args=None):
        """Build args with --root and optional extra args."""
        argv = ["--root", str(ROOT)]
        if extra_args:
            argv.extend(extra_args)
        return builder.parse_args(argv)

    def test_manifest_shape(self) -> None:
        """Verify manifest contains all required top-level fields."""
        args = self._make_args(["--git-commit", "test_sha"])
        manifest = builder.build_manifest(args, Path(tempfile.mkdtemp()))

        self.assertEqual(manifest["bundle_version"], 1)
        self.assertIn("generated_at", manifest)
        self.assertEqual(manifest["git_commit"], "test_sha")
        self.assertIn("summary", manifest)
        self.assertIn("gates", manifest)
        self.assertIn("inputs", manifest)
        self.assertIn("privacy", manifest)

    def test_privacy_attestation(self) -> None:
        args = self._make_args()
        manifest = builder.build_manifest(args, Path(tempfile.mkdtemp()))
        privacy = manifest["privacy"]
        self.assertFalse(privacy["raw_payload_included"])
        self.assertFalse(privacy["contains_pii"])
        self.assertTrue(privacy["redacted"])

    def test_gates_present(self) -> None:
        args = self._make_args()
        manifest = builder.build_manifest(args, Path(tempfile.mkdtemp()))
        gates = manifest["gates"]
        for gate in ("cutover_readiness_ok", "observability_contract_ok", "shadow_evidence_ok", "mirror_evidence_ok"):
            self.assertIn(gate, gates)

    def test_summary_fields(self) -> None:
        args = self._make_args()
        manifest = builder.build_manifest(args, Path(tempfile.mkdtemp()))
        summary = manifest["summary"]
        for field in ("route_count", "legacy_gaps", "chat_parity", "strict_ready"):
            self.assertIn(field, summary)

    def test_local_mode_does_not_require_live_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            args = self._make_args([
                "--shadow-report", str(tmp / "nonexistent.json"),
                "--mirror-report", str(tmp / "nonexistent.json"),
            ])
            try:
                manifest = builder.build_manifest(args, tmp / "bundle")
                self.assertIsNotNone(manifest)
                self.assertFalse(manifest["gates"]["shadow_evidence_ok"])
                self.assertFalse(manifest["gates"]["mirror_evidence_ok"])
            except Exception as exc:
                self.fail(f"local mode should not crash on missing evidence: {exc}")

    def test_strict_mode_requires_live_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bundle_dir = tmp / "bundle"
            bundle_dir.mkdir()
            args = self._make_args([
                "--shadow-report", str(tmp / "nonexistent.json"),
                "--mirror-report", str(tmp / "nonexistent.json"),
                "--strict",
            ])
            with self.assertRaises(ValueError):
                builder.write_bundle_files(args, bundle_dir, builder.build_manifest(args, bundle_dir))

    def test_bundle_files_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bundle_dir = tmp / "bundle"
            bundle_dir.mkdir()
            args = self._make_args()
            manifest = builder.build_manifest(args, bundle_dir)
            manifest_path = bundle_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            builder.write_bundle_files(args, bundle_dir, manifest)

            expected_files = [
                "manifest.json",
                "evidence-summary.md",
                "route-inventory.txt",
                "cutover-readiness.json",
                "observability-contract.json",
            ]
            for fname in expected_files:
                self.assertTrue(
                    (bundle_dir / fname).is_file(),
                    f"missing bundle file: {fname}",
                )

    def test_non_strict_does_not_require_mirror_mode_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bundle_dir = tmp / "bundle"
            bundle_dir.mkdir()
            args = self._make_args()
            manifest = builder.build_manifest(args, bundle_dir)
            summary = manifest["summary"]
            self.assertIsNone(summary.get("strict_ready"))


if __name__ == "__main__":
    unittest.main()
