from dataclasses import dataclass
from datetime import datetime
from .core import RevenueCore


@dataclass(frozen=True)
class RevenueRecord:
    id: str
    timestamp: str
    service_id: str
    amount: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "service_id": self.service_id,
            "amount": self.amount,
            "SIMULATED": True,
        }


class RevenueEngine:
    def __init__(self) -> None:
        self._records: list[RevenueRecord] = []

    def create_record(self, service_id: str, amount: float) -> RevenueRecord:
        if not isinstance(service_id, str) or service_id.strip() == "":
            raise ValueError("service_id must be a non-empty string")
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError("amount must be a numeric value")
        if isinstance(amount, float) and (amount != amount or amount == float('inf') or amount == float('-inf')):
            raise ValueError("amount must be a finite number")
        if amount < 0:
            raise ValueError("amount must be non-negative")

        record_id = RevenueCore.gen_id()
        timestamp = RevenueCore.now_iso()
        record = RevenueRecord(
            id=record_id,
            timestamp=timestamp,
            service_id=service_id,
            amount=float(amount)
        )
        self._records.append(record)
        return record

    def records(self) -> tuple:
        """Return a read-only tuple copy of the stored records."""
        return tuple(self._records)

    def validate_record(self, record: RevenueRecord) -> bool:
        if not isinstance(record, RevenueRecord):
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
        if not isinstance(record.service_id, str) or record.service_id.strip() == "":
            return False
        if not isinstance(record.amount, (int, float)) or isinstance(record.amount, bool):
            return False
        if isinstance(record.amount, float) and (record.amount != record.amount or record.amount == float('inf') or record.amount == float('-inf')):
            return False
        if record.amount < 0:
            return False
        return True
