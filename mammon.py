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
from src.payments import PaymentEngine, verified_revenue
from src.backup import BackupError, create_backup, verify_backup
from src.discovery import DiscoveryError, discover, lead_from_dict, make_lead
from src.matching import MatchingError, build_proposal, rank_matches
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
11) Mark revenue as paid 12) Backup ledger
13) Scan for work       14) Import lead manually
15) Set my skills       16) Match leads & draft proposals
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
        self.payment_engine = PaymentEngine()
        self._load_records()
        self.skills_file = self.data_dir / "skills.json"
        self.leads_file = self.data_dir / "leads.jsonl"

    def load_skills(self):
        try:
            data = json.loads(self.skills_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        skills = data.get("skills", [])
        rate = data.get("hourly_rate", 25.0)
        if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
            return []
        return skills

    def save_skills(self, skills, hourly_rate):
        self.skills_file.write_text(
            json.dumps({"skills": skills, "hourly_rate": hourly_rate}, indent=2),
            encoding="utf-8")

    def load_leads(self):
        leads = []
        try:
            for line in self.leads_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    leads.append(lead_from_dict(json.loads(line)))
        except (OSError, DiscoveryError, ValueError):
            pass
        return leads

    def save_lead(self, lead):
        with self.leads_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(lead.to_dict(), ensure_ascii=False) + "\n")

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
            elif "paid_at" in entry:
                record = self.payment_engine.create_payment(
                    entry["revenue_id"], entry["amount"], entry["paid_at"]
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

    def add_payment(self, revenue_id: str, amount: float, paid_at: str = ""):
        record = self.payment_engine.create_payment(revenue_id, amount, paid_at)
        self.ledger.append(record.to_dict())
        return record

    def backup(self):
        return create_backup(self.ledger.path, self.data_dir / "backups")

    # -- reports ---------------------------------------------------------

    def monthly(self) -> dict:
        return monthly_summary(
            self.revenue_engine.records(),
            self.expense_engine.records(),
            self.fee_engine.records(),
            self.refund_engine.records(),
        )

    def profit(self) -> dict:
        summary = full_profit_summary(
            self.revenue_engine.records(),
            self.expense_engine.records(),
            self.fee_engine.records(),
            self.refund_engine.records(),
        )
        summary["payment_status"] = verified_revenue(
            self.revenue_engine.records(), self.payment_engine.records()
        )
        return summary

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
        for record in self.payment_engine.records():
            rows.append(("payment", "->" + record.revenue_id, record.amount, record.id))
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
            elif choice == "11":
                record = app.add_payment(_ask_str("Revenue id: "),
                                         _ask_float("Amount received: "))
                print(f"  Recorded payment {record.id} (VERIFIED).")
            elif choice == "12":
                manifest = app.backup()
                print(f"  Backup created: {manifest['backup_file']}")
                print(f"  Checksum: {manifest['backup_sha256']}")
                check = verify_backup(Path(manifest["backup_file"]))
                print(f"  Integrity: {check['integrity']}")
            elif choice == "13":
                print("  Scanning public job feeds (offline sources are skipped)...")
                leads = discover()
                for lead in leads[:20]:
                    print(f"  [{lead.source}] {lead.title} ({lead.company})")
                    print(f"    {lead.url}")
                for lead in leads:
                    app.save_lead(lead)
                print(f"  Saved {len(leads)} leads to {self.leads_file if False else app.leads_file}")
            elif choice == "14":
                lead = make_lead(
                    _ask_str("Lead title: "),
                    input("Company (optional): ").strip(),
                    _ask_str("Source (e.g. 'manual'): "),
                    _ask_str("URL: "),
                    input("Description (optional): ").strip(),
                    [t.strip() for t in input("Tags, comma-separated (optional): ").split(",") if t.strip()],
                )
                app.save_lead(lead)
                print(f"  Imported lead {lead.id}.")
            elif choice == "15":
                skills = [s.strip() for s in
                          input("Skills, comma-separated: ").split(",") if s.strip()]
                rate = _ask_float("Target hourly rate: ", allow_zero=False)
                app.save_skills(skills, rate)
                print(f"  Saved {len(skills)} skills.")
            elif choice == "16":
                skills = app.load_skills()
                if not skills:
                    print("  Set your skills first (option 15).")
                else:
                    rate = 25.0
                    try:
                        rate = json.loads(app.skills_file.read_text(encoding="utf-8")).get("hourly_rate", 25.0)
                    except (OSError, ValueError):
                        pass
                    matches = rank_matches(app.load_leads(), skills, rate)
                    if not matches:
                        print("  No leads saved yet; scan (13) or import (14) first.")
                    for m in matches[:5]:
                        print(f"  {m['match_score']:>5} | {m['title']} | est bid ${m['est_bid']}")
                    if matches:
                        pick = input("Draft proposal for which rank # (blank = 1)? ").strip()
                        idx = int(pick) - 1 if pick.isdigit() else 0
                        if 0 <= idx < len(matches):
                            lead = app.load_leads()[idx]
                            proposal = build_proposal(lead, skills, rate)
                            out_file = app.data_dir / f"proposal_{proposal['id'][:8]}.txt"
                            out_file.write_text(proposal["body"] + "\n", encoding="utf-8")
                            print(f"  Proposal draft saved: {out_file}")
                            print("  DRAFT ONLY — review, personalize, and send it yourself.")
            elif choice == "10":
                for kind, label, amount, record_id in app.list_records():
                    print(f"  {kind:<8} {label:<30} {amount:>10.2f}  {record_id}")
                if not app.list_records():
                    print("  (no records)")
            else:
                print("  Unknown option.")
        except (ValueError, ScoringError, InvoiceError, ForecastError, BackupError,
                DiscoveryError, MatchingError) as exc:
            print(f"  [ERROR] {exc}")


if __name__ == "__main__":
    sys.exit(main())
