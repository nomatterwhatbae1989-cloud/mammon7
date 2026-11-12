"""Forecasting for MAMMON-7.

Two kinds of output, never mixed:
- VERIFIED: summaries computed from actual recorded transactions.
- ESTIMATE: scenario projections clearly flagged as estimates.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Iterable

from .revenue import RevenueRecord
from .expenses import ExpenseRecord
from .fees import FeeRecord
from .refunds import RefundRecord


class ForecastError(Exception):
    """Raised when a forecast cannot be computed."""


def _month_key(timestamp: str) -> str:
    if not isinstance(timestamp, str) or not timestamp.strip():
        raise ForecastError("record timestamp must be a non-empty string")
    try:
        parsed = datetime.fromisoformat(
            timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
        )
    except ValueError as exc:
        raise ForecastError(f"invalid timestamp: {timestamp!r}") from exc
    if parsed.tzinfo is None:
        raise ForecastError(f"timestamp lacks timezone info: {timestamp!r}")
    return f"{parsed.year:04d}-{parsed.month:02d}"


def monthly_summary(revenue_records=(), expense_records=(),
                    fee_records=(), refund_records=()) -> dict:
    """Per-month totals computed from actual records (VERIFIED)."""
    months = defaultdict(lambda: {
        "revenue": 0.0, "expenses": 0.0, "fees": 0.0,
        "refunds": 0.0, "net": 0.0,
    })

    for record in revenue_records:
        if not isinstance(record, RevenueRecord):
            raise ForecastError("revenue_records must contain RevenueRecord objects")
        m = months[_month_key(record.timestamp)]
        m["revenue"] += float(record.amount)
        m["net"] += float(record.amount)
    for record in expense_records:
        if not isinstance(record, ExpenseRecord):
            raise ForecastError("expense_records must contain ExpenseRecord objects")
        m = months[_month_key(record.timestamp)]
        m["expenses"] += float(record.amount)
        m["net"] -= float(record.amount)
    for record in fee_records:
        if not isinstance(record, FeeRecord):
            raise ForecastError("fee_records must contain FeeRecord objects")
        m = months[_month_key(record.timestamp)]
        m["fees"] += float(record.amount)
        m["net"] -= float(record.amount)
    for record in refund_records:
        if not isinstance(record, RefundRecord):
            raise ForecastError("refund_records must contain RefundRecord objects")
        m = months[_month_key(record.timestamp)]
        m["refunds"] += float(record.amount)
        m["net"] -= float(record.amount)

    result = {}
    for month in sorted(months):
        data = months[month]
        result[month] = {key: round(value, 2) for key, value in data.items()}
    return {"months": result, "basis": "VERIFIED_RECORDS"}


def project_from_records(revenue_records, expense_records=(),
                        fee_records=(), refund_records=(),
                        months_ahead: int = 6) -> dict:
    """Project future months by extending the average net of recorded months.

    Clearly an ESTIMATE: it assumes the recorded months are representative.
    With fewer than 2 recorded months it refuses to project.
    """
    if not isinstance(months_ahead, int) or isinstance(months_ahead, bool) \
            or months_ahead < 1 or months_ahead > 60:
        raise ForecastError("months_ahead must be an integer from 1 to 60")

    summary = monthly_summary(revenue_records, expense_records,
                              fee_records, refund_records)
    recorded = summary["months"]
    if len(recorded) < 2:
        raise ForecastError(
            "need at least 2 recorded months before projecting; "
            "keep recording real transactions first"
        )

    net_values = [data["net"] for data in recorded.values()]
    average_net = sum(net_values) / len(net_values)

    projections = {}
    last_month = max(recorded)
    year, month = int(last_month[:4]), int(last_month[5:7])
    for _ in range(months_ahead):
        month += 1
        if month > 12:
            month = 1
            year += 1
        projections[f"{year:04d}-{month:02d}"] = round(average_net, 2)

    return {
        "recorded_months": len(recorded),
        "average_monthly_net": round(average_net, 2),
        "projected_months": projections,
        "projected_total_net": round(average_net * months_ahead, 2),
        "basis": "ESTIMATE_FROM_VERIFIED_RECORDS",
        "ESTIMATE": True,
    }


def scenario_model(average_monthly_net: float, months: int = 12,
                   conservative: float = 0.5, base: float = 1.0,
                   optimistic: float = 2.0) -> dict:
    """Simple scenario model from an average net figure (ESTIMATE).

    Multipliers are assumptions, not predictions.
    """
    average = float(average_monthly_net)
    if average != average or average in (float("inf"), float("-inf")):
        raise ForecastError("average_monthly_net must be finite")
    if not isinstance(months, int) or isinstance(months, bool) or months < 1:
        raise ForecastError("months must be a positive integer")
    for name, mult in (("conservative", conservative),
                       ("base", base), ("optimistic", optimistic)):
        if not isinstance(mult, (int, float)) or isinstance(mult, bool) or mult < 0:
            raise ForecastError(f"{name} multiplier must be a non-negative number")

    return {
        "months": months,
        "conservative": round(average * conservative * months, 2),
        "base": round(average * base * months, 2),
        "optimistic": round(average * optimistic * months, 2),
        "ESTIMATE": True,
        "note": "Scenario projections are assumptions, not guarantees.",
    }
