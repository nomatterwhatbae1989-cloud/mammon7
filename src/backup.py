"""Backup and export for MAMMON-7 ledger data.

Backups are non-destructive: a backup never overwrites an existing file,
and the original ledger is never modified.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class BackupError(Exception):
    """Raised when a backup cannot be created."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def create_backup(ledger_path, backup_dir) -> dict:
    """Copy the ledger to a timestamped backup file plus a manifest.

    Refuses to overwrite any existing file. Returns backup details.
    """
    if isinstance(ledger_path, str):
        ledger_path = Path(ledger_path)
    if isinstance(backup_dir, str):
        backup_dir = Path(backup_dir)
    if not isinstance(ledger_path, Path) or not isinstance(backup_dir, Path):
        raise BackupError("paths must be str or pathlib.Path")
    if not ledger_path.is_file():
        raise BackupError(f"ledger not found: {ledger_path}")

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"mammon7_backup_{stamp}.jsonl"

    if backup_file.exists():
        raise BackupError(f"backup already exists: {backup_file}")

    shutil.copyfile(ledger_path, backup_file)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_ledger": str(ledger_path),
        "backup_file": str(backup_file),
        "ledger_sha256": _sha256(ledger_path),
        "backup_sha256": _sha256(backup_file),
        "ledger_bytes": ledger_path.stat().st_size,
    }
    manifest_file = backup_dir / f"mammon7_backup_{stamp}.manifest.json"
    if manifest_file.exists():
        raise BackupError(f"manifest already exists: {manifest_file}")
    manifest_file.write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    if manifest["ledger_sha256"] != manifest["backup_sha256"]:
        raise BackupError("backup checksum mismatch; original is untouched")
    return manifest


def verify_backup(backup_path) -> dict:
    """Verify a backup file is intact by recomputing its checksum.

    The manifest next to the backup must contain the expected sha256.
    """
    if isinstance(backup_path, str):
        backup_path = Path(backup_path)
    if not isinstance(backup_path, Path):
        raise BackupError("path must be str or pathlib.Path")
    if not backup_path.is_file():
        raise BackupError(f"backup not found: {backup_path}")

    manifest_file = backup_path.with_name(
        backup_path.name.replace(".jsonl", ".manifest.json")
    )
    if not manifest_file.is_file():
        raise BackupError(f"manifest not found: {manifest_file}")

    manifest = json.loads(
        manifest_file.read_text(encoding="utf-8")
    )
    actual = _sha256(backup_path)
    ok = actual == manifest.get("backup_sha256")
    return {
        "backup_file": str(backup_path),
        "integrity": "OK" if ok else "FAILED",
        "expected_sha256": manifest.get("backup_sha256"),
        "actual_sha256": actual,
    }
