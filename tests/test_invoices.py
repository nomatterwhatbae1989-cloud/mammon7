import unittest

from src.fees import FeeEngine
from src.refunds import RefundEngine
from src.invoices import InvoiceError, build_invoice, invoice_to_text
from src.revenue import RevenueEngine


def make_revenue(amount, service_id="svc"):
    return RevenueEngine().create_record(service_id, amount)


class TestBuildInvoice(unittest.TestCase):

    def test_basic_invoice(self):
        invoice = build_invoice("Acme Corp", [make_revenue(100), make_revenue(50)])
        self.assertEqual(len(invoice["id"]), 32)
        self.assertEqual(invoice["customer_name"], "Acme Corp")
        self.assertEqual(len(invoice["line_items"]), 2)
        self.assertAlmostEqual(invoice["subtotal"], 150.0)
        self.assertAlmostEqual(invoice["fees_total"], 0.0)
        self.assertAlmostEqual(invoice["refunds_total"], 0.0)
        self.assertAlmostEqual(invoice["total_due"], 150.0)
        self.assertIs(invoice["SIMULATED"], True)

    def test_invoice_with_fees_and_refunds(self):
        revenue = [make_revenue(200)]
        fees = [FeeEngine().create_fee(revenue[0].id, 30)]
        refunds = [RefundEngine().create_refund(revenue[0].id, 20, "partial")]
        invoice = build_invoice("Acme Corp", revenue, fees, refunds)
        self.assertAlmostEqual(invoice["subtotal"], 200.0)
        self.assertAlmostEqual(invoice["fees_total"], 30.0)
        self.assertAlmostEqual(invoice["refunds_total"], 20.0)
        self.assertAlmostEqual(invoice["total_due"], 150.0)

    def test_custom_invoice_id_and_notes(self):
        invoice = build_invoice("Acme", [make_revenue(10)],
                                invoice_id="INV-001", notes="net 30")
        self.assertEqual(invoice["id"], "INV-001")
        self.assertEqual(invoice["notes"], "net 30")

    def test_blank_invoice_id_generates_one(self):
        invoice = build_invoice("Acme", [make_revenue(10)], invoice_id="   ")
        self.assertEqual(len(invoice["id"]), 32)

    def test_empty_customer_name_rejected(self):
        for bad in ("", "   ", 42, None):
            with self.subTest(customer=bad):
                with self.assertRaises(InvoiceError):
                    build_invoice(bad, [make_revenue(10)])

    def test_no_revenue_records_rejected(self):
        with self.assertRaises(InvoiceError):
            build_invoice("Acme", [])

    def test_wrong_record_types_rejected(self):
        with self.assertRaises(InvoiceError):
            build_invoice("Acme", [make_revenue(10), "fake"])
        with self.assertRaises(InvoiceError):
            build_invoice("Acme", [make_revenue(10)], fee_records=["fake"])
        with self.assertRaises(InvoiceError):
            build_invoice("Acme", [make_revenue(10)], refund_records=["fake"])

    def test_negative_total_due_possible(self):
        revenue = [make_revenue(50)]
        fees = [FeeEngine().create_fee(revenue[0].id, 80)]
        invoice = build_invoice("Acme", revenue, fees)
        self.assertAlmostEqual(invoice["total_due"], -30.0)


class TestInvoiceText(unittest.TestCase):

    def test_renders_all_sections(self):
        revenue = [make_revenue(100, "web-design")]
        fees = [FeeEngine().create_fee(revenue[0].id, 20)]
        refunds = [RefundEngine().create_refund(revenue[0].id, 10, "goodwill")]
        invoice = build_invoice("Acme Corp", revenue, fees, refunds, notes="thanks")
        text = invoice_to_text(invoice)
        self.assertIn("INVOICE", text)
        self.assertIn("Acme Corp", text)
        self.assertIn("Service web-design", text)
        self.assertIn("Subtotal: 100.00", text)
        self.assertIn("Platform fees: 20.00", text)
        self.assertIn("Refunds: 10.00", text)
        self.assertIn("TOTAL DUE: 70.00", text)
        self.assertIn("SIMULATED INVOICE", text)
        self.assertIn("Notes: thanks", text)

    def test_rejects_non_dict(self):
        with self.assertRaises(InvoiceError):
            invoice_to_text("not a dict")

    def test_rejects_incomplete_dict(self):
        with self.assertRaises(InvoiceError):
            invoice_to_text({"id": "x"})


if __name__ == "__main__":
    unittest.main()
