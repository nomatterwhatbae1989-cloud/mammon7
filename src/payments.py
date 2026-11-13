"""Verified payment records for MAMMON-7.

A PaymentRecord marks revenue as ACTUALLY RECEIVED. Payments are the
only records that carry VERIFIED: True — they represent real money in,
never estimates. Amounts are capped to the gross revenue they settle.
"""
from __future__ import annotations

from datetime import datetime

from .core import RevenueCore


class PaymentRecord:
    __slots__ = ("id", "timestamp", "revenue_id", "amount", "paid_at")

    def __init__(self, id: str, timestamp: str, revenue_id: str,
                 amount: float, paid_at: str) -> None:
        self.id = id
        self.timestamp = timestamp
        self.revenue_id = revenue_id
        self.amount = amount
        self.paid_at = paid_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "revenue_id": self.revenue_id,
            "amount": self.amount,
            "paid_at": self.paid_at,
            "VERIFIED": True,
        }

    def __eq__(self, other) -> bool:
        if not isinstance(other, PaymentRecord):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (f"PaymentRecord(id={self.id!r}, revenue_id={self.revenue_id!r}, "
                f"amount={self.amount!r}, paid_at={self.paid_at!r})")


def _validate_amount(amount) -> None:
    if not isinstance(amount, (int, float)) or isinstance(amount, bool):
        raise ValueError("amount must be a numeric value")
    if isinstance(amount, float) and (amount != amount or amount == float('inf') or amount == float('-inf')):
        raise ValueError("amount must be a finite number")
    if amount < 0:
        raise ValueError("amount must be non-negative")


def _validate_timestamp(value) -> str:
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("timestamp must be a non-empty string")
    try:
        parsed = datetime.fromisoformat(
            value[:-1] + "+00:00" if value.endswith("Z") else value
        )
    except ValueError as exc:
        raise ValueError(f"invalid timestamp: {value!r}") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone information")
    return value


class PaymentEngine:
    def __init__(self) -> None:
        self._records: list = []

    def create_payment(self, revenue_id: str, amount: float,
                       paid_at: str = "") -> PaymentRecord:
        """Record a real payment received against a revenue record."""
        if not isinstance(revenue_id, str) or revenue_id.strip() == "":
            raise ValueError("revenue_id must be a non-empty string")
        _validate_amount(amount)
        if not isinstance(paid_at, str):
            raise ValueError("paid_at must be a string")
        paid_at = paid_at.strip() or RevenueCore.now_iso()
        _validate_timestamp(paid_at)
        record = PaymentRecord(
            id=RevenueCore.gen_id(),
            timestamp=RevenueCore.now_iso(),
            revenue_id=revenue_id,
            amount=float(amount),
            paid_at=paid_at,
        )
        self._records.append(record)
        return record

    def create_payment_capped(self, revenue_id: str, amount: float,
                               gross_amount: float,
                               paid_at: str = "") -> PaymentRecord:
        """Record a payment that can never exceed the gross revenue amount."""
        _validate_amount(gross_amount)
        capped = min(float(amount), float(gross_amount))
        return self.create_payment(revenue_id, capped, paid_at)

    def records(self) -> tuple:
        return tuple(self._records)

    def total_for(self, revenue_id: str) -> float:
        if not isinstance(revenue_id, str) or revenue_id.strip() == "":
            raise ValueError("revenue_id must be a non-empty string")
        return sum(record.amount for record in self._records
                   if record.revenue_id == revenue_id)

    def validate_record(self, record: PaymentRecord) -> bool:
        if not isinstance(record, PaymentRecord):
            return False
        if not isinstance(record.id, str) or record.id.strip() == "":
            return False
        if not isinstance(record.timestamp, str) or record.timestamp.strip() == "":
            return False
        try:
            parsed = datetime.fromisoformat(
                record.timestamp[:-1] + "+00:00"
                if record.timestamp.endswith("Z") else record.timestamp
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
        if not isinstance(record.paid_at, str) or record.paid_at.strip() == "":
            return False
        try:
            paid = datetime.fromisoformat(
                record.paid_at[:-1] + "+00:00"
                if record.paid_at.endswith("Z") else record.paid_at
            )
        except ValueError:
            return False
        if paid.tzinfo is None:
            return False
        return True


def verified_revenue(revenue_records, payment_records) -> dict:
    """Split revenue into verified (paid) and outstanding (unpaid) totals.

    A revenue record counts as verified up to the sum of payments made
    against it; anything beyond the payments is outstanding.
    """
    payments_by_revenue: dict = {}
    for payment in payment_records:
        if not isinstance(payment, PaymentRecord):
            raise TypeError("payment_records must contain PaymentRecord objects")
        payments_by_revenue[payment.revenue_id] = (
            payments_by_revenue.get(payment.revenue_id, 0.0) + payment.amount
        )

    verified = 0.0
    outstanding = 0.0
    for record in revenue_records:
        paid = min(float(record.amount),
                   payments_by_revenue.get(record.id, 0.0))
        verified += paid
        outstanding += float(record.amount) - paid

    return {
        "gross_revenue": round(verified + outstanding, 2),
        "verified_revenue": round(verified, 2),
        "outstanding_revenue": round(outstanding, 2),
        "VERIFIED_BASIS": True,
    }
