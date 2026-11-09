from dataclasses import dataclass
from datetime import datetime
from .core import RevenueCore


@dataclass(frozen=True)
class ExpenseRecord:
    id: str
    timestamp: str
    category: str
    amount: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "amount": self.amount,
            "SIMULATED": True,
        }


class ExpenseEngine:
    def __init__(self) -> None:
        self._records: list[ExpenseRecord] = []

    def create_record(self, category: str, amount: float) -> ExpenseRecord:
        if not isinstance(category, str) or category.strip() == "":
            raise ValueError("category must be a non-empty string")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("amount must be a numeric value")
        if isinstance(amount, float) and (amount != amount or amount == float('inf') or amount == float('-inf')):
            raise ValueError("amount must be a finite number")
        if amount < 0:
            raise ValueError("amount must be non-negative")

        record_id = RevenueCore.gen_id()
        timestamp = RevenueCore.now_iso()
        record = ExpenseRecord(
            id=record_id,
            timestamp=timestamp,
            category=category,
            amount=float(amount)
        )
        self._records.append(record)
        return record

    def validate_record(self, record: ExpenseRecord) -> bool:
        if not isinstance(record, ExpenseRecord):
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
        if not isinstance(record.category, str) or record.category.strip() == "":
            return False
        if not isinstance(record.amount, (int, float)) or isinstance(record.amount, bool):
            return False
        if isinstance(record.amount, float) and (record.amount != record.amount or record.amount == float('inf') or record.amount == float('-inf')):
            return False
        if record.amount < 0:
            return False
        return True
