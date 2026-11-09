"""SIMULATED invoice generation for MAMMON-7 revenue engine."""
from __future__ import annotations

from typing import Iterable, List

from .core import RevenueCore
from .fees import FeeRecord
from .refunds import RefundRecord
from .revenue import RevenueRecord


class InvoiceError(Exception):
    """Raised when an invoice cannot be built from the given records."""


def build_invoice(
    customer_name: str,
    revenue_records: Iterable[RevenueRecord],
    fee_records: Iterable[FeeRecord] = (),
    refund_records: Iterable[RefundRecord] = (),
    invoice_id: str = "",
    notes: str = "",
) -> dict:
    """Build a SIMULATED invoice dict from revenue, fee, and refund records.

    The invoice records what MAMMON would bill; it does not claim payment.
    """
    if not isinstance(customer_name, str) or customer_name.strip() == "":
        raise InvoiceError("customer_name must be a non-empty string")
    if invoice_id is None:
        invoice_id = ""
    if not isinstance(invoice_id, str):
        raise InvoiceError("invoice_id must be a string")
    if not isinstance(notes, str):
        raise InvoiceError("notes must be a string")

    revenue = list(revenue_records)
    fees = list(fee_records)
    refunds = list(refund_records)

    for record in revenue:
        if not isinstance(record, RevenueRecord):
            raise InvoiceError("revenue_records must contain RevenueRecord objects")
    for record in fees:
        if not isinstance(record, FeeRecord):
            raise InvoiceError("fee_records must contain FeeRecord objects")
    for record in refunds:
        if not isinstance(record, RefundRecord):
            raise InvoiceError("refund_records must contain RefundRecord objects")

    if not revenue:
        raise InvoiceError("an invoice requires at least one revenue record")

    subtotal = sum(float(record.amount) for record in revenue)
    fees_total = sum(float(record.amount) for record in fees)
    refunds_total = sum(float(record.amount) for record in refunds)
    total_due = round(subtotal - fees_total - refunds_total, 2)

    invoice = {
        "id": invoice_id.strip() or RevenueCore.gen_id(),
        "timestamp": RevenueCore.now_iso(),
        "customer_name": customer_name,
        "line_items": [
            {
                "description": f"Service {record.service_id}",
                "revenue_id": record.id,
                "amount": float(record.amount),
            }
            for record in revenue
        ],
        "fees": [
            {"fee_id": record.id, "revenue_id": record.revenue_id, "amount": float(record.amount)}
            for record in fees
        ],
        "refunds": [
            {"refund_id": record.id, "revenue_id": record.revenue_id,
             "amount": float(record.amount), "reason": record.reason}
            for record in refunds
        ],
        "subtotal": round(subtotal, 2),
        "fees_total": round(fees_total, 2),
        "refunds_total": round(refunds_total, 2),
        "total_due": total_due,
        "notes": notes,
        "SIMULATED": True,
    }
    return invoice


def invoice_to_text(invoice: dict) -> str:
    """Render an invoice dict as plain text."""
    if not isinstance(invoice, dict):
        raise InvoiceError("invoice must be a dict")
    required = {"id", "timestamp", "customer_name", "line_items",
                "subtotal", "fees_total", "refunds_total", "total_due"}
    missing = required - set(invoice.keys())
    if missing:
        raise InvoiceError(f"invoice missing keys: {sorted(missing)}")

    lines = [
        f"INVOICE {invoice['id']}",
        f"Date: {invoice['timestamp']}",
        f"Billed to: {invoice['customer_name']}",
        "",
        "Line items:",
    ]
    for item in invoice["line_items"]:
        lines.append(f"  - {item['description']}: {item['amount']:.2f}")
    lines += [
        "",
        f"Subtotal: {invoice['subtotal']:.2f}",
        f"Platform fees: {invoice['fees_total']:.2f}",
        f"Refunds: {invoice['refunds_total']:.2f}",
        f"TOTAL DUE: {invoice['total_due']:.2f}",
    ]
    if invoice.get("notes"):
        lines += ["", f"Notes: {invoice['notes']}"]
    lines += ["", "SIMULATED INVOICE - no payment has been received or requested."]
    return "\n".join(lines) + "\n"
