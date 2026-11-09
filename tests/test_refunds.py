import unittest

from src.refunds import RefundEngine, RefundRecord


class TestRefundCreation(unittest.TestCase):

    def setUp(self):
        self.engine = RefundEngine()

    def test_create_valid_refund(self):
        refund = self.engine.create_refund("rev-1", 25.0, "customer request")
        self.assertEqual(refund.revenue_id, "rev-1")
        self.assertEqual(refund.amount, 25.0)
        self.assertEqual(refund.reason, "customer request")

    def test_reason_defaults_to_empty(self):
        refund = self.engine.create_refund("rev-1", 25.0)
        self.assertEqual(refund.reason, "")

    def test_capped_refund_limits_to_gross(self):
        refund = self.engine.create_refund_capped("rev-1", 150.0, 100.0, "over-refund")
        self.assertEqual(refund.amount, 100.0)

    def test_capped_refund_allows_partial(self):
        refund = self.engine.create_refund_capped("rev-1", 30.0, 100.0)
        self.assertEqual(refund.amount, 30.0)

    def test_invalid_amounts_rejected(self):
        for bad in ("10", True, -1, float("nan"), float("inf"), None):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_refund("rev-1", bad)

    def test_invalid_revenue_ids_rejected(self):
        for bad in ("", "   ", 123, None):
            with self.subTest(revenue_id=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_refund(bad, 5.0)

    def test_non_string_reason_rejected(self):
        with self.assertRaises(ValueError):
            self.engine.create_refund("rev-1", 5.0, reason=42)

    def test_to_dict_simulated_flag(self):
        refund = self.engine.create_refund("rev-1", 5.0, "test")
        data = refund.to_dict()
        self.assertIs(data["SIMULATED"], True)
        self.assertEqual(set(data.keys()),
                         {"id", "timestamp", "revenue_id", "amount", "reason", "SIMULATED"})

    def test_total_for_filters_by_revenue_id(self):
        self.engine.create_refund("rev-1", 10)
        self.engine.create_refund("rev-1", 15)
        self.engine.create_refund("rev-2", 50)
        self.assertAlmostEqual(self.engine.total_for("rev-1"), 25.0)
        self.assertAlmostEqual(self.engine.total_for("rev-2"), 50.0)

    def test_records_accessor(self):
        self.engine.create_refund("rev-1", 10)
        self.assertEqual(len(self.engine.records()), 1)


class TestRefundValidation(unittest.TestCase):

    def setUp(self):
        self.engine = RefundEngine()

    def make_record(self, **overrides):
        fields = {"id": "d" * 32, "timestamp": "2026-01-01T00:00:00.000Z",
                  "revenue_id": "rev-1", "amount": 5.0, "reason": "test"}
        fields.update(overrides)
        return RefundRecord(**fields)

    def test_valid_created_record_passes(self):
        refund = self.engine.create_refund("rev-1", 5.0)
        self.assertTrue(self.engine.validate_record(refund))

    def test_valid_manually_built_record_passes(self):
        self.assertTrue(self.engine.validate_record(self.make_record()))

    def test_invalid_records_rejected(self):
        cases = [
            {"id": ""},
            {"id": 123},
            {"timestamp": ""},
            {"timestamp": "garbage"},
            {"revenue_id": ""},
            {"reason": 42},
            {"amount": "5"},
            {"amount": True},
            {"amount": -1},
            {"amount": float("nan")},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.assertFalse(
                    self.engine.validate_record(self.make_record(**overrides))
                )

    def test_non_record_rejected(self):
        self.assertFalse(self.engine.validate_record(None))
        self.assertFalse(self.engine.validate_record("nope"))


if __name__ == "__main__":
    unittest.main()
