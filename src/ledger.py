"""Append-only JSONL ledger persistence for MAMMON-7 revenue engine."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .revenue import RevenueRecord
from .expenses import ExpenseRecord


class LedgerError(Exception):
    """Raised when ledger data is malformed or an entry cannot be persisted."""


def _require_mapping(entry: Any) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise LedgerError("ledger entries must be dictionaries")
    return entry


def revenue_from_dict(data: Dict[str, Any]) -> RevenueRecord:
    """Rebuild a RevenueRecord from a serialized dict. Raises LedgerError on bad shape."""
    _require_mapping(data)
    missing = {"id", "timestamp", "service_id", "amount"} - set(data.keys())
    if missing:
        raise LedgerError(f"revenue entry missing keys: {sorted(missing)}")
    try:
        return RevenueRecord(
            id=data["id"],
            timestamp=data["timestamp"],
            service_id=data["service_id"],
            amount=data["amount"],
        )
    except TypeError as exc:
        raise LedgerError(f"invalid revenue entry: {exc}") from exc


def expense_from_dict(data: Dict[str, Any]) -> ExpenseRecord:
    """Rebuild an ExpenseRecord from a serialized dict. Raises LedgerError on bad shape."""
    _require_mapping(data)
    missing = {"id", "timestamp", "category", "amount"} - set(data.keys())
    if missing:
        raise LedgerError(f"expense entry missing keys: {sorted(missing)}")
    try:
        return ExpenseRecord(
            id=data["id"],
            timestamp=data["timestamp"],
            category=data["category"],
            amount=data["amount"],
        )
    except TypeError as exc:
        raise LedgerError(f"invalid expense entry: {exc}") from exc


class Ledger:
    """Append-only JSONL file ledger.

    Never rewrites or deletes existing lines; new entries are appended only.
    """

    def __init__(self, path) -> None:
        if isinstance(path, str):
            path = Path(path)
        if not isinstance(path, Path):
            raise TypeError("path must be a str or pathlib.Path")
        self._path = path
        if self._path.parent and not self._path.parent.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: Dict[str, Any]) -> None:
        _require_mapping(entry)
        line = json.dumps(entry, ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def append_records(self, records: Iterable[Any]) -> int:
        count = 0
        for record in records:
            if not hasattr(record, "to_dict"):
                raise LedgerError("records must provide to_dict()")
            self.append(record.to_dict())
            count += 1
        return count

    def read_all(self) -> List[Dict[str, Any]]:
        if not self._path.exists():
            return []
        entries: List[Dict[str, Any]] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except ValueError as exc:
                    raise LedgerError(
                        f"malformed JSON at {self._path}:{line_number}: {exc}"
                    ) from exc
                if not isinstance(parsed, dict):
                    raise LedgerError(
                        f"non-object entry at {self._path}:{line_number}"
                    )
                entries.append(parsed)
        return entries

    def revenue_records(self) -> List[RevenueRecord]:
        return [
            revenue_from_dict(entry)
            for entry in self.read_all()
            if "service_id" in entry
        ]

    def expense_records(self) -> List[ExpenseRecord]:
        return [
            expense_from_dict(entry)
            for entry in self.read_all()
            if "category" in entry
        ]
