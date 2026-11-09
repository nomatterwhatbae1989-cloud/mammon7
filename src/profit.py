"""Net profit calculations over revenue and expense records."""
from __future__ import annotations

import math
from typing import Iterable

from .revenue import RevenueRecord
from .expenses import ExpenseRecord


def _sum_amounts(records: Iterable, expected_type) -> float:
    total = 0.0
    for record in records:
        if not isinstance(record, expected_type):
            raise TypeError(
                f"expected {expected_type.__name__}, got {type(record).__name__}"
            )
        amount = record.amount
        if not isinstance(amount, (int, float)) or isinstance(amount, bool):
            raise ValueError(f"record {record.id!r} has a non-numeric amount")
        if not math.isfinite(amount) or amount < 0:
            raise ValueError(f"record {record.id!r} has an invalid amount")
        total += float(amount)
    return total


def total_revenue(records: Iterable[RevenueRecord]) -> float:
    return _sum_amounts(records, RevenueRecord)


def total_expenses(records: Iterable[ExpenseRecord]) -> float:
    return _sum_amounts(records, ExpenseRecord)


def net_profit(
    revenue_records: Iterable[RevenueRecord],
    expense_records: Iterable[ExpenseRecord],
) -> float:
    return total_revenue(revenue_records) - total_expenses(expense_records)


def profit_summary(
    revenue_records: Iterable[RevenueRecord],
    expense_records: Iterable[ExpenseRecord],
) -> dict:
    revenue = total_revenue(revenue_records)
    expenses = total_expenses(expense_records)
    return {
        "total_revenue": revenue,
        "total_expenses": expenses,
        "net_profit": revenue - expenses,
        "SIMULATED": True,
    }


def net_profit_full(
    revenue_records: Iterable[RevenueRecord],
    expense_records: Iterable[ExpenseRecord],
    fee_records: Iterable = (),
    refund_records: Iterable = (),
) -> float:
    """Net profit accounting for expenses, platform fees, and refunds.

    net = gross revenue - expenses - fees - refunds
    """
    from .fees import FeeRecord
    from .refunds import RefundRecord

    gross = total_revenue(revenue_records)
    expenses = total_expenses(expense_records)
    fees = _sum_amounts(fee_records, FeeRecord)
    refunds = _sum_amounts(refund_records, RefundRecord)
    return gross - expenses - fees - refunds


def full_profit_summary(
    revenue_records: Iterable[RevenueRecord],
    expense_records: Iterable[ExpenseRecord],
    fee_records: Iterable = (),
    refund_records: Iterable = (),
) -> dict:
    """Complete money picture: revenue, expenses, fees, refunds, net.

    All figures are SIMULATED estimates unless built from verified records.
    """
    from .fees import FeeRecord
    from .refunds import RefundRecord

    gross = total_revenue(revenue_records)
    expenses = total_expenses(expense_records)
    fees = _sum_amounts(fee_records, FeeRecord)
    refunds = _sum_amounts(refund_records, RefundRecord)
    return {
        "gross_revenue": gross,
        "total_expenses": expenses,
        "platform_fees": fees,
        "refunds": refunds,
        "net_profit": gross - expenses - fees - refunds,
        "SIMULATED": True,
    }
