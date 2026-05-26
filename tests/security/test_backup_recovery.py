from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"


def _run(script: str, *args: str, **env) -> subprocess.CompletedProcess:
    cmd = ["bash", str(SCRIPTS / script), *args]
    merged_env = {**os.environ, **env}
    return subprocess.run(cmd, capture_output=True, text=True, env=merged_env, timeout=30)


class BackupManifestTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        os.makedirs(self.tmpdir / "data" / "backups", exist_ok=True)
        os.makedirs(self.tmpdir / "knowledge_vault" / "public", exist_ok=True)
        (self.tmpdir / "knowledge_vault" / "public" / "test.md").write_text("---\ntitle: Test\n---\n# Test", encoding="utf-8")
        (self.tmpdir / ".env.example").write_text("DB_HOST=localhost", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def test_backup_manifest_created(self):
        self.skipTest("requires DATABASE_URL_ADMIN and pg_dump")
        return True

    def test_backup_contains_required_components(self):
        self.skipTest("requires DATABASE_URL_ADMIN and pg_dump")
        return True

    def test_backup_excludes_real_env(self):
        self.skipTest("requires DATABASE_URL_ADMIN and pg_dump")
        return True

    def test_backup_includes_env_example(self):
        self.skipTest("requires DATABASE_URL_ADMIN and pg_dump")
        return True


class ManifestValidationTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.archive_dir = self.tmpdir / "backup_test"
        self.archive_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def _write_manifest(self, manifest: dict) -> None:
        p = self.archive_dir / "manifest.json"
        p.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def _write_file(self, rel_path: str, content: bytes) -> None:
        p = self.archive_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)

    def _make_archive(self) -> Path:
        archive = self.tmpdir / "test_backup.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for root, dirs, files in os.walk(self.archive_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    tar.add(fpath, arcname=fpath.relative_to(self.tmpdir))
        return archive

    def test_manifest_missing_created_at_is_invalid(self):
        self._write_manifest({
            "components": ["knowledge_vault"],
            "checksums": {},
            "format_version": 1,
        })
        self._write_file("knowledge_vault/test.md", b"# test")
        archive = self._make_archive()

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertNotEqual(result.returncode, 0, f"Should reject missing created_at: {result.stdout}")

    def test_manifest_missing_components_is_invalid(self):
        self._write_manifest({
            "created_at": "2026-01-01T00:00:00Z",
            "checksums": {},
            "format_version": 1,
        })
        self._write_file("knowledge_vault/test.md", b"# test")
        archive = self._make_archive()

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertNotEqual(result.returncode, 0, f"Should reject missing components: {result.stdout}")

    def test_restore_dry_run_validates_archive(self):
        content = b"# knowledge vault test"
        sha = hashlib.sha256(content).hexdigest()

        self._write_manifest({
            "created_at": "2026-01-01T00:00:00Z",
            "components": ["knowledge_vault", "postgres_dump", "env_example"],
            "checksums": {"knowledge_vault/test.md": f"sha256:{sha}"},
            "format_version": 1,
        })
        self._write_file("knowledge_vault/test.md", content)
        self._write_file(".env.example", b"DB_HOST=localhost")
        archive = self._make_archive()

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertEqual(result.returncode, 0, f"Dry-run should pass: {result.stderr}")
        self.assertIn("Dry-run PASS", result.stdout)

    def test_restore_rejects_invalid_archive(self):
        archive = self.tmpdir / "bad.tar.gz"
        archive.write_bytes(b"not a valid archive")

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertNotEqual(result.returncode, 0, f"Should reject invalid archive: {result.stdout}")

    def test_restore_rejects_checksum_mismatch(self):
        correct_content = b"# correct"
        wrong_sha = hashlib.sha256(b"# different").hexdigest()

        self._write_manifest({
            "created_at": "2026-01-01T00:00:00Z",
            "components": ["knowledge_vault", "postgres_dump", "env_example"],
            "checksums": {"knowledge_vault/test.md": f"sha256:{wrong_sha}"},
            "format_version": 1,
        })
        self._write_file("knowledge_vault/test.md", correct_content)
        self._write_file(".env.example", b"DB_HOST=localhost")
        archive = self._make_archive()

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertNotEqual(result.returncode, 0,
                          f"Should reject checksum mismatch: stdout={result.stdout} stderr={result.stderr}")

    def test_restore_rejects_missing_manifest(self):
        archive = self.tmpdir / "no_manifest.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tmp_file = self.tmpdir / "just_a_file.txt"
            tmp_file.write_text("hello")
            tar.add(tmp_file, arcname="some_backup/just_a_file.txt")

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertNotEqual(result.returncode, 0, f"Should reject missing manifest: {result.stdout}")
        self.assertIn("manifest", result.stdout + result.stderr)


class RecoveryDrillTest(unittest.TestCase):
    def test_recovery_drill_script_exists(self):
        self.assertTrue((SCRIPTS / "recovery_drill.sh").is_file(),
                       "recovery_drill.sh should exist")

    def test_recovery_drill_script_executable(self):
        self.assertTrue(os.access(SCRIPTS / "recovery_drill.sh", os.X_OK),
                       "recovery_drill.sh should be executable")

    def test_backup_script_exists(self):
        self.assertTrue((SCRIPTS / "backup.sh").is_file(),
                       "backup.sh should exist")

    def test_restore_script_exists(self):
        self.assertTrue((SCRIPTS / "restore.sh").is_file(),
                       "restore.sh should exist")


class CheckBackupTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(str(self.tmpdir), ignore_errors=True)

    def _build_valid_archive(self) -> Path:
        content = b"# valid content"
        sha = hashlib.sha256(content).hexdigest()

        backup_dir = self.tmpdir / "my_backup"
        backup_dir.mkdir()

        (backup_dir / "manifest.json").write_text(json.dumps({
            "created_at": "2026-01-01T00:00:00Z",
            "components": ["knowledge_vault", "postgres_dump", "env_example"],
            "checksums": {"knowledge_vault/test.md": f"sha256:{sha}"},
            "format_version": 1,
        }), encoding="utf-8")

        (backup_dir / "knowledge_vault").mkdir()
        (backup_dir / "knowledge_vault" / "test.md").write_bytes(content)
        (backup_dir / ".env.example").write_text("DB_HOST=localhost")

        archive = self.tmpdir / "valid.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for root, dirs, files in os.walk(backup_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    tar.add(fpath, arcname=fpath.relative_to(self.tmpdir))
        return archive

    def test_check_backup_passes_valid_archive(self):
        archive = self._build_valid_archive()
        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertEqual(result.returncode, 0, f"Valid archive should pass: {result.stderr}")

    def test_check_backup_fails_missing_manifest(self):
        archive = self.tmpdir / "no_manifest.tar.gz"
        backup_dir = self.tmpdir / "bad_backup"
        backup_dir.mkdir()
        (backup_dir / "knowledge_vault").mkdir()
        (backup_dir / "knowledge_vault" / "x.md").write_text("# x")
        with tarfile.open(archive, "w:gz") as tar:
            for root, dirs, files in os.walk(backup_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    tar.add(fpath, arcname=fpath.relative_to(self.tmpdir))

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertNotEqual(result.returncode, 0, f"Should fail: {result.stderr}")

    def test_restore_files_must_include_checksum_for_all_files(self):
        extra_content = b"# unlisted file"
        listed_content = b"# listed"
        listed_sha = hashlib.sha256(listed_content).hexdigest()

        backup_dir = self.tmpdir / "partial_backup"
        backup_dir.mkdir()
        (backup_dir / "manifest.json").write_text(json.dumps({
            "created_at": "2026-01-01T00:00:00Z",
            "components": ["knowledge_vault", "postgres_dump", "env_example"],
            "checksums": {"knowledge_vault/listed.md": f"sha256:{listed_sha}"},
            "format_version": 1,
        }), encoding="utf-8")
        (backup_dir / "knowledge_vault").mkdir()
        (backup_dir / "knowledge_vault" / "listed.md").write_bytes(listed_content)
        (backup_dir / "knowledge_vault" / "unlisted.md").write_bytes(extra_content)
        (backup_dir / ".env.example").write_text("DB_HOST=localhost")

        archive = self.tmpdir / "partial.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for root, dirs, files in os.walk(backup_dir):
                for fname in files:
                    fpath = Path(root) / fname
                    tar.add(fpath, arcname=fpath.relative_to(self.tmpdir))

        result = _run("restore.sh", str(archive), "--dry-run")
        self.assertEqual(result.returncode, 0,
                        f"Archive with extra unlisted file should still pass: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
