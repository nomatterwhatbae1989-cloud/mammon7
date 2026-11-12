#!/usr/bin/env python3
"""MAMMON-7 revenue engine CLI.

Interactive terminal front-end for the revenue engine.
All records are SIMULATED unless they come from your real verified sales.
Standard library only. No payments, no external calls.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.core import RevenueCore
from src.revenue import RevenueEngine, RevenueRecord
from src.expenses import ExpenseEngine, ExpenseRecord
from src.fees import FeeEngine
from src.refunds import RefundEngine
from src.ledger import Ledger
from src.profit import full_profit_summary
from src.forecast import ForecastError, monthly_summary, project_from_records
from src.scoring import ScoringError, create_opportunity, score_opportunity
from src.invoices import build_invoice, invoice_to_text, InvoiceError

DATA_DIR = Path.home() / "mammon7_data"
LEDGER_FILE = "records.jsonl"

MENU = """
==== MAMMON-7 Revenue Engine (SIMULATED DATA) ====
 1) Add revenue          5) Monthly summary
 2) Add expense          6) Full profit summary
 3) Add platform fee     7) Score an opportunity
 4) Add refund           8) Build an invoice
 9) Forecast             10) List records
 q) Quit
"""


class App:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.ledger = Ledger(self.data_dir / LEDGER_FILE)
        self.revenue_engine = RevenueEngine()
        self.expense_engine = ExpenseEngine()
        self.fee_engine = FeeEngine()
        self.refund_engine = RefundEngine()
        self._load_records()

    def _load_records(self) -> None:
        for entry in self.ledger.read_all():
            if "service_id" in entry:
                self.revenue_engine._records.append(RevenueRecord(
                    id=entry["id"], timestamp=entry["timestamp"],
                    service_id=entry["service_id"], amount=float(entry["amount"]),
                ))
            elif "category" in entry:
                self.expense_engine._records.append(ExpenseRecord(
                    id=entry["id"], timestamp=entry["timestamp"],
                    category=entry["category"], amount=float(entry["amount"]),
                ))
            elif "reason" in entry:
                record = self.refund_engine.create_refund(
                    entry["revenue_id"], entry["amount"], entry.get("reason", "")
                )
                record.id = entry["id"]
                record.timestamp = entry["timestamp"]
            elif "revenue_id" in entry:
                record = self.fee_engine.create_fee(
                    entry["revenue_id"], entry["amount"]
                )
                record.id = entry["id"]
                record.timestamp = entry["timestamp"]
            else:
                continue

    # -- record creation -------------------------------------------------

    def add_revenue(self, service_id: str, amount: float):
        record = self.revenue_engine.create_record(service_id, amount)
        self.ledger.append(record.to_dict())
        return record

    def add_expense(self, category: str, amount: float):
        record = self.expense_engine.create_record(category, amount)
        self.ledger.append(record.to_dict())
        return record

    def add_fee(self, revenue_id: str, amount: float):
        record = self.fee_engine.create_fee(revenue_id, amount)
        self.ledger.append(record.to_dict())
        return record

    def add_refund(self, revenue_id: str, amount: float, reason: str = ""):
        record = self.refund_engine.create_refund(revenue_id, amount, reason)
        self.ledger.append(record.to_dict())
        return record

    # -- reports ---------------------------------------------------------

    def monthly(self) -> dict:
        return monthly_summary(
            self.revenue_engine.records(),
            self.expense_engine.records(),
            self.fee_engine.records(),
            self.refund_engine.records(),
        )

    def profit(self) -> dict:
        return full_profit_summary(
            self.revenue_engine.records(),
            self.expense_engine.records(),
            self.fee_engine.records(),
            self.refund_engine.records(),
        )

    def forecast(self, months_ahead: int = 6) -> dict:
        return project_from_records(
            self.revenue_engine.records(),
            self.expense_engine.records(),
            self.fee_engine.records(),
            self.refund_engine.records(),
            months_ahead=months_ahead,
        )

    def invoice(self, customer_name: str) -> dict:
        revenue = list(self.revenue_engine.records())
        if not revenue:
            raise InvoiceError("no revenue records yet; add revenue first")
        fees = [f for f in self.fee_engine.records()]
        refunds = [r for r in self.refund_engine.records()]
        return build_invoice(customer_name, revenue, fees, refunds)

    def list_records(self) -> list:
        rows = []
        for record in self.revenue_engine.records():
            rows.append(("revenue", record.service_id, record.amount, record.id))
        for record in self.expense_engine.records():
            rows.append(("expense", record.category, record.amount, record.id))
        for record in self.fee_engine.records():
            rows.append(("fee", "->" + record.revenue_id, record.amount, record.id))
        for record in self.refund_engine.records():
            rows.append(("refund", "->" + record.revenue_id, record.amount, record.id))
        return rows


def _ask_float(prompt: str, allow_zero: bool = True) -> float:
    while True:
        raw = input(prompt).strip()
        try:
            value = float(raw)
        except ValueError:
            print("  Please enter a number.")
            continue
        if value < 0 or (not allow_zero and value <= 0):
            print("  Value must be non-negative.")
            continue
        if value != value or value in (float("inf"), float("-inf")):
            print("  Value must be finite.")
            continue
        return value


def _ask_str(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("  Please enter a non-empty value.")


def main() -> int:
    parser = argparse.ArgumentParser(description="MAMMON-7 revenue engine CLI")
    parser.add_argument("--data-dir", default=str(DATA_DIR),
                        help="directory for the JSONL ledger")
    args = parser.parse_args()

    app = App(args.data_dir)

    while True:
        print(MENU)
        try:
            choice = input("Select> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("Bye.")
            return 0

        try:
            if choice in ("q", "quit", "exit"):
                print("Bye.")
                return 0
            elif choice == "1":
                record = app.add_revenue(_ask_str("Service id: "),
                                         _ask_float("Amount: "))
                print(f"  Recorded revenue {record.id} (SIMULATED).")
            elif choice == "2":
                record = app.add_expense(_ask_str("Category: "),
                                         _ask_float("Amount: "))
                print(f"  Recorded expense {record.id} (SIMULATED).")
            elif choice == "3":
                record = app.add_fee(_ask_str("Revenue id: "),
                                    _ask_float("Fee amount: "))
                print(f"  Recorded fee {record.id} (SIMULATED).")
            elif choice == "4":
                record = app.add_refund(_ask_str("Revenue id: "),
                                        _ask_float("Refund amount: "),
                                        input("Reason (optional): ").strip())
                print(f"  Recorded refund {record.id} (SIMULATED).")
            elif choice == "5":
                print(json.dumps(app.monthly(), indent=2))
            elif choice == "6":
                print(json.dumps(app.profit(), indent=2))
            elif choice == "7":
                title = _ask_str("Opportunity title: ")
                kind = _ask_str("Kind (service/product): ")
                print("Rate 1-10 (10 = high demand, crowded, expert skills):")
                opp = create_opportunity(
                    title, kind,
                    _ask_float("  est_demand 1-10: "),
                    _ask_float("  competition 1-10: "),
                    _ask_float("  skills_required 1-10: "),
                    _ask_float("  time_hours: "),
                    _ask_float("  startup_cost: "),
                    _ask_float("  est_price: "),
                    _ask_float("  est_delivery_cost: "),
                )
                print(json.dumps(score_opportunity(opp), indent=2))
            elif choice == "8":
                invoice = app.invoice(_ask_str("Customer name: "))
                print(invoice_to_text(invoice))
            elif choice == "9":
                months = int(_ask_float("Months ahead: "))
                print(json.dumps(app.forecast(months), indent=2))
            elif choice == "10":
                for kind, label, amount, record_id in app.list_records():
                    print(f"  {kind:<8} {label:<30} {amount:>10.2f}  {record_id}")
                if not app.list_records():
                    print("  (no records)")
            else:
                print("  Unknown option.")
        except (ValueError, ScoringError, InvoiceError, ForecastError) as exc:
            print(f"  [ERROR] {exc}")


if __name__ == "__main__":
    sys.exit(main())
