import re
import unittest

from src.core import RevenueCore


class TestRevenueCore(unittest.TestCase):

    def test_now_iso_format(self):
        stamp = RevenueCore.now_iso()
        self.assertTrue(isinstance(stamp, str))
        self.assertRegex(stamp, r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")

    def test_now_iso_parseable_utc(self):
        from datetime import datetime, timezone
        parsed = datetime.fromisoformat(
            RevenueCore.now_iso().replace("Z", "+00:00")
        )
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset().total_seconds(), 0)
        self.assertEqual(parsed.tzinfo, timezone.utc)

    def test_now_iso_advances(self):
        first = RevenueCore.now_iso()
        second = RevenueCore.now_iso()
        self.assertGreaterEqual(second, first)

    def test_gen_id_length_and_charset(self):
        for _ in range(10):
            self.assertRegex(RevenueCore.gen_id(), r"^[0-9a-f]{32}$")

    def test_gen_id_unique(self):
        ids = {RevenueCore.gen_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)


if __name__ == "__main__":
    unittest.main()
