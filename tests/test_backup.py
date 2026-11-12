import json
import tempfile
import unittest
from pathlib import Path

from src.backup import BackupError, create_backup, verify_backup


class TestCreateBackup(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Path(self.tmp.name) / "records.jsonl"
        self.ledger.write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
        self.backup_dir = Path(self.tmp.name) / "backups"

    def test_backup_created_with_manifest(self):
        manifest = create_backup(self.ledger, self.backup_dir)
        backup_file = Path(manifest["backup_file"])
        self.assertTrue(backup_file.is_file())
        self.assertEqual(backup_file.read_text(encoding="utf-8"),
                         self.ledger.read_text(encoding="utf-8"))
        manifest_file = backup_file.with_name(
            backup_file.name.replace(".jsonl", ".manifest.json"))
        self.assertTrue(manifest_file.is_file())
        self.assertEqual(manifest["ledger_sha256"], manifest["backup_sha256"])

    def test_backup_is_copy_not_move(self):
        create_backup(self.ledger, self.backup_dir)
        self.assertTrue(self.ledger.is_file())
        self.assertEqual(self.ledger.read_text(encoding="utf-8"),
                         '{"a": 1}\n{"b": 2}\n')

    def test_missing_ledger_rejected(self):
        with self.assertRaises(BackupError):
            create_backup(Path(self.tmp.name) / "nope.jsonl", self.backup_dir)

    def test_bad_path_types_rejected(self):
        with self.assertRaises(BackupError):
            create_backup(123, self.backup_dir)
        with self.assertRaises(BackupError):
            create_backup(self.ledger, 456)

    def test_verify_backup_ok(self):
        manifest = create_backup(self.ledger, self.backup_dir)
        result = verify_backup(manifest["backup_file"])
        self.assertEqual(result["integrity"], "OK")

    def test_verify_backup_detects_tampering(self):
        manifest = create_backup(self.ledger, self.backup_dir)
        backup_file = Path(manifest["backup_file"])
        backup_file.write_text('{"a": 999}\n', encoding="utf-8")
        result = verify_backup(backup_file)
        self.assertEqual(result["integrity"], "FAILED")

    def test_verify_missing_files_rejected(self):
        with self.assertRaises(BackupError):
            verify_backup(Path(self.tmp.name) / "nope.jsonl")
        manifest = create_backup(self.ledger, self.backup_dir)
        backup_file = Path(manifest["backup_file"])
        backup_file.with_name(
            backup_file.name.replace(".jsonl", ".manifest.json")).unlink()
        with self.assertRaises(BackupError):
            verify_backup(backup_file)


if __name__ == "__main__":
    unittest.main()
