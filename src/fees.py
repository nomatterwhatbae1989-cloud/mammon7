"""Platform fee records for MAMMON-7 revenue engine."""
from __future__ import annotations

from datetime import datetime

from .core import RevenueCore


class FeeRecord:
    __slots__ = ("id", "timestamp", "revenue_id", "amount")

    def __init__(self, id: str, timestamp: str, revenue_id: str, amount: float) -> None:
        self.id = id
        self.timestamp = timestamp
        self.revenue_id = revenue_id
        self.amount = amount

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "revenue_id": self.revenue_id,
            "amount": self.amount,
            "SIMULATED": True,
        }

    def __eq__(self, other) -> bool:
        if not isinstance(other, FeeRecord):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"FeeRecord(id={self.id!r}, revenue_id={self.revenue_id!r}, amount={self.amount!r})"


def _validate_amount(amount) -> None:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise ValueError("amount must be a numeric value")
    if isinstance(amount, float) and (amount != amount or amount == float('inf') or amount == float('-inf')):
        raise ValueError("amount must be a finite number")
    if amount < 0:
        raise ValueError("amount must be non-negative")


class FeeEngine:
    def __init__(self) -> None:
        self._records: list = []

    def create_fee(self, revenue_id: str, amount: float) -> FeeRecord:
        if not isinstance(revenue_id, str) or revenue_id.strip() == "":
            raise ValueError("revenue_id must be a non-empty string")
        _validate_amount(amount)
        record = FeeRecord(
            id=RevenueCore.gen_id(),
            timestamp=RevenueCore.now_iso(),
            revenue_id=revenue_id,
            amount=float(amount),
        )
        self._records.append(record)
        return record

    def create_percentage_fee(self, revenue_id: str, gross_amount: float, rate: float) -> FeeRecord:
        if not isinstance(rate, (int, float)) or isinstance(rate, bool):
            raise ValueError("rate must be a numeric value")
        if isinstance(rate, float) and (rate != rate or rate == float('inf') or rate == float('-inf')):
            raise ValueError("rate must be a finite number")
        if rate < 0:
            raise ValueError("rate must be non-negative")
        _validate_amount(gross_amount)
        fee = round(float(gross_amount) * float(rate), 2)
        return self.create_fee(revenue_id, fee)

    def records(self) -> tuple:
        return tuple(self._records)

    def total_for(self, revenue_id: str) -> float:
        if not isinstance(revenue_id, str) or revenue_id.strip() == "":
            raise ValueError("revenue_id must be a non-empty string")
        return sum(record.amount for record in self._records if record.revenue_id == revenue_id)

    def validate_record(self, record: FeeRecord) -> bool:
        if not isinstance(record, FeeRecord):
            return False
        if not isinstance(record.id, str) or record.id.strip() == "":
            return False
        if not isinstance(record.timestamp, str) or record.timestamp.strip() == "":
            return False
        try:
            parsed = datetime.fromisoformat(
                record.timestamp[:-1] + "+00:00"
                if record.timestamp.endswith("Z")
                else record.timestamp
            )
        except ValueError:
            return False
        if parsed.tzinfo is None:
            return False
        if not isinstance(record.revenue_id, str) or record.revenue_id.strip() == "":
            return False
        if not isinstance(record.amount, (int, float)) or isinstance(record.amount, bool):
            return False
        if isinstance(record.amount, float) and (record.amount != record.amount or record.amount == float('inf') or record.amount == float('-inf')):
            return False
        if record.amount < 0:
            return False
        return True
