import unittest

from src.payments import PaymentEngine, PaymentRecord, verified_revenue
from src.revenue import RevenueEngine


class TestPaymentCreation(unittest.TestCase):

    def setUp(self):
        self.engine = PaymentEngine()

    def test_create_valid_payment(self):
        payment = self.engine.create_payment("rev-1", 100.0)
        self.assertEqual(payment.revenue_id, "rev-1")
        self.assertEqual(payment.amount, 100.0)
        self.assertTrue(payment.paid_at.endswith("Z"))
        self.assertTrue(payment.timestamp.endswith("Z"))

    def test_custom_paid_at(self):
        payment = self.engine.create_payment(
            "rev-1", 50, paid_at="2026-01-15T10:00:00.000Z")
        self.assertEqual(payment.paid_at, "2026-01-15T10:00:00.000Z")

    def test_capped_payment_limits_to_gross(self):
        payment = self.engine.create_payment_capped("rev-1", 150, 100)
        self.assertEqual(payment.amount, 100.0)

    def test_capped_payment_allows_partial(self):
        payment = self.engine.create_payment_capped("rev-1", 40, 100)
        self.assertEqual(payment.amount, 40.0)

    def test_to_dict_is_verified(self):
        payment = self.engine.create_payment("rev-1", 10)
        data = payment.to_dict()
        self.assertIs(data["VERIFIED"], True)
        self.assertNotIn("SIMULATED", data)
        self.assertEqual(set(data.keys()),
                         {"id", "timestamp", "revenue_id", "amount",
                          "paid_at", "VERIFIED"})

    def test_invalid_amounts_rejected(self):
        for bad in ("10", True, -1, float("nan"), float("inf"), None):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_payment("rev-1", bad)

    def test_invalid_revenue_ids_rejected(self):
        for bad in ("", "   ", 123, None):
            with self.subTest(revenue_id=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_payment(bad, 5.0)

    def test_invalid_paid_at_rejected(self):
        for bad in ("garbage", "2026-01-01", 42, None):
            with self.subTest(paid_at=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_payment("rev-1", 5.0, paid_at=bad)

    def test_blank_paid_at_defaults_to_now(self):
        payment = self.engine.create_payment("rev-1", 5.0, paid_at="   ")
        self.assertTrue(payment.paid_at.endswith("Z"))

    def test_total_for(self):
        self.engine.create_payment("rev-1", 10)
        self.engine.create_payment("rev-1", 15)
        self.engine.create_payment("rev-2", 100)
        self.assertAlmostEqual(self.engine.total_for("rev-1"), 25.0)
        self.assertAlmostEqual(self.engine.total_for("rev-2"), 100.0)


class TestPaymentValidation(unittest.TestCase):

    def setUp(self):
        self.engine = PaymentEngine()

    def make_record(self, **overrides):
        fields = {"id": "e" * 32, "timestamp": "2026-01-01T00:00:00.000Z",
                  "revenue_id": "rev-1", "amount": 5.0,
                  "paid_at": "2026-01-02T00:00:00.000Z"}
        fields.update(overrides)
        return PaymentRecord(**fields)

    def test_valid_created_record_passes(self):
        payment = self.engine.create_payment("rev-1", 5.0)
        self.assertTrue(self.engine.validate_record(payment))

    def test_valid_manually_built_record_passes(self):
        self.assertTrue(self.engine.validate_record(self.make_record()))

    def test_invalid_records_rejected(self):
        cases = [
            {"id": ""},
            {"timestamp": ""},
            {"timestamp": "not-a-date"},
            {"revenue_id": ""},
            {"amount": "5"},
            {"amount": True},
            {"amount": -1},
            {"paid_at": ""},
            {"paid_at": "garbage"},
            {"paid_at": "2026-01-01T00:00:00"},  # naive
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.assertFalse(
                    self.engine.validate_record(self.make_record(**overrides))
                )

    def test_non_record_rejected(self):
        self.assertFalse(self.engine.validate_record("nope"))
        self.assertFalse(self.engine.validate_record(None))


class TestVerifiedRevenue(unittest.TestCase):

    def test_fully_paid(self):
        revenue = RevenueEngine().create_record("svc", 100)
        payments = PaymentEngine()
        payments.create_payment(revenue.id, 100)
        result = verified_revenue([revenue], payments.records())
        self.assertAlmostEqual(result["verified_revenue"], 100.0)
        self.assertAlmostEqual(result["outstanding_revenue"], 0.0)
        self.assertIs(result["VERIFIED_BASIS"], True)

    def test_partially_paid(self):
        revenue = RevenueEngine().create_record("svc", 100)
        payments = PaymentEngine()
        payments.create_payment(revenue.id, 40)
        result = verified_revenue([revenue], payments.records())
        self.assertAlmostEqual(result["verified_revenue"], 40.0)
        self.assertAlmostEqual(result["outstanding_revenue"], 60.0)

    def test_unpaid(self):
        revenue = RevenueEngine().create_record("svc", 100)
        result = verified_revenue([revenue], [])
        self.assertAlmostEqual(result["verified_revenue"], 0.0)
        self.assertAlmostEqual(result["outstanding_revenue"], 100.0)

    def test_overpayment_capped_at_revenue(self):
        revenue = RevenueEngine().create_record("svc", 100)
        payments = PaymentEngine()
        payments.create_payment(revenue.id, 150)
        result = verified_revenue([revenue], payments.records())
        self.assertAlmostEqual(result["verified_revenue"], 100.0)
        self.assertAlmostEqual(result["outstanding_revenue"], 0.0)

    def test_multiple_payments_accumulate(self):
        revenue = RevenueEngine().create_record("svc", 100)
        payments = PaymentEngine()
        payments.create_payment(revenue.id, 30)
        payments.create_payment(revenue.id, 30)
        result = verified_revenue([revenue], payments.records())
        self.assertAlmostEqual(result["verified_revenue"], 60.0)

    def test_rejects_wrong_types(self):
        with self.assertRaises(TypeError):
            verified_revenue([], ["nope"])


if __name__ == "__main__":
    unittest.main()
