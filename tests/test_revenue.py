import unittest
from dataclasses import FrozenInstanceError

from src.revenue import RevenueEngine, RevenueRecord


class TestRevenueRecordCreation(unittest.TestCase):

    def setUp(self):
        self.engine = RevenueEngine()

    def test_create_valid_record(self):
        record = self.engine.create_record("web-design", 250.0)
        self.assertEqual(record.service_id, "web-design")
        self.assertEqual(record.amount, 250.0)
        self.assertEqual(len(record.id), 32)
        self.assertTrue(record.timestamp.endswith("Z"))

    def test_create_record_accepts_int_amount(self):
        record = self.engine.create_record("consulting", 100)
        self.assertEqual(record.amount, 100.0)
        self.assertIsInstance(record.amount, float)

    def test_create_record_accepts_zero(self):
        record = self.engine.create_record("free-review", 0)
        self.assertEqual(record.amount, 0.0)

    def test_to_dict_serialization_simulated_flag(self):
        record = self.engine.create_record("web-design", 99.5)
        data = record.to_dict()
        self.assertEqual(
            set(data.keys()),
            {"id", "timestamp", "service_id", "amount", "SIMULATED"},
        )
        self.assertIs(data["SIMULATED"], True)
        self.assertEqual(data["service_id"], "web-design")
        self.assertEqual(data["amount"], 99.5)

    def test_invalid_amounts_rejected(self):
        for bad in ("10", True, False, -1, -0.01, float("nan"),
                    float("inf"), float("-inf"), None, [5]):
            with self.subTest(amount=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_record("svc", bad)

    def test_invalid_service_ids_rejected(self):
        for bad in ("", "   ", 123, None):
            with self.subTest(service_id=bad):
                with self.assertRaises(ValueError):
                    self.engine.create_record(bad, 10.0)

    def test_record_is_frozen(self):
        record = self.engine.create_record("svc", 10.0)
        with self.assertRaises(FrozenInstanceError):
            record.amount = 999.0
        with self.assertRaises(FrozenInstanceError):
            record.service_id = "other"


class TestRevenueValidateRecord(unittest.TestCase):

    def setUp(self):
        self.engine = RevenueEngine()

    def make_record(self, **overrides):
        fields = {
            "id": "a" * 32,
            "timestamp": "2026-01-01T00:00:00.000Z",
            "service_id": "svc",
            "amount": 10.0,
        }
        fields.update(overrides)
        return RevenueRecord(**fields)

    def test_valid_created_record_passes(self):
        record = self.engine.create_record("svc", 10.0)
        self.assertTrue(self.engine.validate_record(record))

    def test_valid_manually_built_record_passes(self):
        self.assertTrue(self.engine.validate_record(self.make_record()))

    def test_non_record_object_rejected(self):
        self.assertFalse(self.engine.validate_record("not a record"))
        self.assertFalse(self.engine.validate_record(None))

    def test_empty_id_rejected(self):
        record = self.make_record(id="")
        self.assertFalse(self.engine.validate_record(record))

    def test_whitespace_id_rejected(self):
        record = self.make_record(id="   ")
        self.assertFalse(self.engine.validate_record(record))

    def test_non_string_id_rejected(self):
        for bad in (123, None, 1.5, ["abc"]):
            with self.subTest(id=bad):
                self.assertFalse(
                    self.engine.validate_record(self.make_record(id=bad))
                )

    def test_missing_timestamp_rejected(self):
        self.assertFalse(
            self.engine.validate_record(self.make_record(timestamp=""))
        )
        self.assertFalse(
            self.engine.validate_record(self.make_record(timestamp="   "))
        )
        self.assertFalse(
            self.engine.validate_record(self.make_record(timestamp=None))
        )

    def test_malformed_timestamp_rejected(self):
        for bad in ("not-a-date", "2026-13-45T99:99:99Z",
                    "2026-01-01", "01/01/2026", "2026-01-01T00:00:00."):
            with self.subTest(timestamp=bad):
                self.assertFalse(
                    self.engine.validate_record(self.make_record(timestamp=bad))
                )

    def test_timezone_naive_timestamp_rejected(self):
        record = self.make_record(timestamp="2026-01-01T00:00:00.000")
        self.assertFalse(self.engine.validate_record(record))

    def test_timezone_aware_timestamps_accepted(self):
        for good in ("2026-01-01T00:00:00.000Z",
                     "2026-01-01T00:00:00.000+00:00",
                     "2026-01-01T00:00:00.000+05:30",
                     "2026-01-01T00:00:00-08:00"):
            with self.subTest(timestamp=good):
                self.assertTrue(
                    self.engine.validate_record(self.make_record(timestamp=good))
                )

    def test_invalid_amount_rejected_in_validation(self):
        for bad in ("10", True, -5, float("nan"), float("inf")):
            with self.subTest(amount=bad):
                self.assertFalse(
                    self.engine.validate_record(self.make_record(amount=bad))
                )

    def test_invalid_service_id_rejected_in_validation(self):
        self.assertFalse(
            self.engine.validate_record(self.make_record(service_id=""))
        )
        self.assertFalse(
            self.engine.validate_record(self.make_record(service_id="  "))
        )
        self.assertFalse(
            self.engine.validate_record(self.make_record(service_id=123))
        )


if __name__ == "__main__":
    unittest.main()
