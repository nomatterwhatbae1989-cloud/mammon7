import unittest

from src.fees import FeeEngine, FeeRecord


class TestFeeCreation(unittest.TestCase):

    def setUp(self):
        self.engine = FeeEngine()

    def test_create_valid_fee(self):
        fee = self.engine.create_fee("rev-1", 12.5)
        self.assertEqual(fee.revenue_id, "rev-1")
        self.assertEqual(fee.amount, 12.5)
        self.assertEqual(len(fee.id), 32)
        self.assertTrue(fee.timestamp.endswith("Z"))

    def test_create_fee_accepts_zero(self):
        fee = self.engine.create_fee("rev-1", 0)
        self.assertEqual(fee.amount, 0.0)

    def test_percentage_fee(self):
        fee = self.engine.create_percentage_fee("rev-1", 100.0, 0.2)
        self.assertAlmostEqual(fee.amount, 20.0)

    def test_percentage_fee_rounds_to_cents(self):
        fee = self.engine.create_percentage_fee("rev-1", 33.33, 0.15)
        self.assertEqual(fee.amount, 5.0)

    def test_percentage_fee_rejects_bad_rate(self):
        for bad in ("0.2", True, -0.1, float("nan"), float("inf")):
            with self.subTest(rate=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_percentage_fee("rev-1", 100, bad)

    def test_invalid_amounts_rejected(self):
        for bad in ("10", True, -1, float("nan"), float("inf"), float("-inf"), None):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_fee("rev-1", bad)

    def test_invalid_revenue_ids_rejected(self):
        for bad in ("", "   ", 123, None):
            with self.subTest(revenue_id=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_fee(bad, 5.0)

    def test_to_dict_simulated_flag(self):
        fee = self.engine.create_fee("rev-1", 5.0)
        data = fee.to_dict()
        self.assertIs(data["SIMULATED"], True)
        self.assertEqual(set(data.keys()),
                         {"id", "timestamp", "revenue_id", "amount", "SIMULATED"})

    def test_records_accessor_is_copy(self):
        self.engine.create_fee("rev-1", 5)
        records = self.engine.records()
        self.engine.create_fee("rev-1", 6)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(self.engine.records()), 2)

    def test_total_for_filters_by_revenue_id(self):
        self.engine.create_fee("rev-1", 5)
        self.engine.create_fee("rev-1", 7)
        self.engine.create_fee("rev-2", 100)
        self.assertAlmostEqual(self.engine.total_for("rev-1"), 12.0)
        self.assertAlmostEqual(self.engine.total_for("rev-2"), 100.0)
        self.assertAlmostEqual(self.engine.total_for("rev-3"), 0.0)


class TestFeeValidation(unittest.TestCase):

    def setUp(self):
        self.engine = FeeEngine()

    def make_record(self, **overrides):
        fields = {"id": "c" * 32, "timestamp": "2026-01-01T00:00:00.000Z",
                  "revenue_id": "rev-1", "amount": 5.0}
        fields.update(overrides)
        return FeeRecord(**fields)

    def test_valid_created_record_passes(self):
        fee = self.engine.create_fee("rev-1", 5.0)
        self.assertTrue(self.engine.validate_record(fee))

    def test_valid_manually_built_record_passes(self):
        self.assertTrue(self.engine.validate_record(self.make_record()))

    def test_invalid_records_rejected(self):
        cases = [
            {"id": ""},
            {"id": "   "},
            {"id": 123},
            {"timestamp": ""},
            {"timestamp": "not-a-date"},
            {"revenue_id": ""},
            {"revenue_id": 42},
            {"amount": "5"},
            {"amount": True},
            {"amount": -1},
            {"amount": float("nan")},
            {"amount": float("inf")},
        ]
        for overrides in cases:
            with self.subTest(**overrides):
                self.assertFalse(
                    self.engine.validate_record(self.make_record(**overrides))
                )

    def test_non_record_rejected(self):
        self.assertFalse(self.engine.validate_record("nope"))
        self.assertFalse(self.engine.validate_record(None))


if __name__ == "__main__":
    unittest.main()
