import json
import tempfile
import unittest
from pathlib import Path

from src.ledger import Ledger, LedgerError, expense_from_dict, revenue_from_dict
from src.revenue import RevenueEngine, RevenueRecord
from src.expenses import ExpenseEngine, ExpenseRecord


class TestLedgerAppendRead(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "ledger.jsonl"
        self.ledger = Ledger(self.path)

    def test_read_all_empty_when_no_file(self):
        self.assertEqual(self.ledger.read_all(), [])

    def test_append_and_read_all_roundtrip(self):
        engine = RevenueEngine()
        record = engine.create_record("web-design", 150.0)
        self.ledger.append(record.to_dict())
        entries = self.ledger.read_all()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["service_id"], "web-design")
        self.assertIs(entries[0]["SIMULATED"], True)

    def test_append_records_multiple(self):
        re = RevenueEngine()
        ee = ExpenseEngine()
        count = self.ledger.append_records([
            re.create_record("a", 10),
            re.create_record("b", 20),
            ee.create_record("software", 5),
        ])
        self.assertEqual(count, 3)
        self.assertEqual(len(self.ledger.read_all()), 3)

    def test_append_rejects_non_dict(self):
        for bad in ("x", 42, None, [1]):
            with self.subTest(entry=bad):
                with self.assertRaises(LedgerError):
                    self.ledger.append(bad)

    def test_append_records_rejects_plain_objects(self):
        with self.assertRaises(LedgerError):
            self.ledger.append_records(["not a record"])

    def test_append_is_never_destructive(self):
        re = RevenueEngine()
        self.ledger.append(re.create_record("a", 1).to_dict())
        first_line = self.path.read_text(encoding="utf-8")
        self.ledger.append(re.create_record("b", 2).to_dict())
        content = self.path.read_text(encoding="utf-8")
        self.assertTrue(content.startswith(first_line))
        self.assertEqual(len(content.strip().splitlines()), 2)

    def test_read_all_rejects_malformed_json(self):
        self.path.write_text("{not json}\n", encoding="utf-8")
        with self.assertRaises(LedgerError):
            self.ledger.read_all()

    def test_read_all_rejects_non_object_lines(self):
        self.path.write_text("[1, 2]\n", encoding="utf-8")
        with self.assertRaises(LedgerError):
            self.ledger.read_all()

    def test_blank_lines_skipped(self):
        self.path.write_text("\n{ \"a\": 1 }\n\n", encoding="utf-8")
        self.assertEqual(self.ledger.read_all(), [{"a": 1}])

    def test_creates_parent_directories(self):
        deep = Path(self.tmp.name) / "a" / "b" / "ledger.jsonl"
        ledger = Ledger(deep)
        ledger.append({"x": 1})
        self.assertTrue(deep.exists())

    def test_rejects_bad_path_type(self):
        with self.assertRaises(TypeError):
            Ledger(123)


class TestLedgerRecordReconstruction(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ledger = Ledger(Path(self.tmp.name) / "ledger.jsonl")

    def test_revenue_roundtrip_preserves_fields(self):
        record = RevenueEngine().create_record("consulting", 75.5)
        self.ledger.append(record.to_dict())
        rebuilt = self.ledger.revenue_records()[0]
        self.assertEqual(rebuilt, record)

    def test_expense_roundtrip_preserves_fields(self):
        record = ExpenseEngine().create_record("hosting", 9.99)
        self.ledger.append(record.to_dict())
        rebuilt = self.ledger.expense_records()[0]
        self.assertEqual(rebuilt, record)

    def test_mixed_ledger_separates_types(self):
        re, ee = RevenueEngine(), ExpenseEngine()
        self.ledger.append_records([
            re.create_record("a", 100),
            ee.create_record("software", 25),
            re.create_record("b", 50),
        ])
        self.assertEqual(len(self.ledger.revenue_records()), 2)
        self.assertEqual(len(self.ledger.expense_records()), 1)

    def test_revenue_from_dict_missing_keys(self):
        with self.assertRaises(LedgerError):
            revenue_from_dict({"id": "x"})

    def test_expense_from_dict_missing_keys(self):
        with self.assertRaises(LedgerError):
            expense_from_dict({"id": "x"})

    def test_from_dict_rejects_non_dict(self):
        with self.assertRaises(LedgerError):
            revenue_from_dict("nope")
        with self.assertRaises(LedgerError):
            expense_from_dict(42)


class TestEngineRecordsAccessor(unittest.TestCase):

    def test_revenue_records_accessor(self):
        engine = RevenueEngine()
        engine.create_record("a", 1)
        engine.create_record("b", 2)
        records = engine.records()
        self.assertEqual(len(records), 2)
        self.assertIsInstance(records, tuple)

    def test_accessor_returns_copy(self):
        engine = RevenueEngine()
        engine.create_record("a", 1)
        records = engine.records()
        engine.create_record("b", 2)
        self.assertEqual(len(records), 1)
        self.assertEqual(len(engine.records()), 2)

    def test_expense_records_accessor(self):
        engine = ExpenseEngine()
        engine.create_record("software", 5)
        self.assertEqual(len(engine.records()), 1)


if __name__ == "__main__":
    unittest.main()
