import unittest

from src.profit import net_profit, profit_summary, total_expenses, total_revenue
from src.revenue import RevenueEngine, RevenueRecord
from src.expenses import ExpenseEngine, ExpenseRecord


def make_revenue(amount, service_id="svc"):
    return RevenueEngine().create_record(service_id, amount)


def make_expense(amount, category="software"):
    return ExpenseEngine().create_record(category, amount)


class TestTotals(unittest.TestCase):

    def test_total_revenue_sums(self):
        records = [make_revenue(100), make_revenue(49.5), make_revenue(0)]
        self.assertAlmostEqual(total_revenue(records), 149.5)

    def test_total_revenue_empty(self):
        self.assertEqual(total_revenue([]), 0.0)

    def test_total_expenses_sums(self):
        records = [make_expense(30), make_expense(19.99)]
        self.assertAlmostEqual(total_expenses(records), 49.99)

    def test_total_expenses_empty(self):
        self.assertEqual(total_expenses([]), 0.0)

    def test_wrong_type_rejected(self):
        with self.assertRaises(TypeError):
            total_revenue([make_expense(10)])
        with self.assertRaises(TypeError):
            total_expenses([make_revenue(10)])

    def test_invalid_record_rejected(self):
        bad = RevenueRecord(
            id="x" * 32,
            timestamp="2026-01-01T00:00:00.000Z",
            service_id="svc",
            amount=-5,
        )
        with self.assertRaises(ValueError):
            total_revenue([bad])
        bad_exp = ExpenseRecord(
            id="x" * 32,
            timestamp="2026-01-01T00:00:00.000Z",
            category="software",
            amount=float("nan"),
        )
        with self.assertRaises(ValueError):
            total_expenses([bad_exp])


class TestNetProfit(unittest.TestCase):

    def test_positive_net_profit(self):
        revenue = [make_revenue(500)]
        expenses = [make_expense(120)]
        self.assertAlmostEqual(net_profit(revenue, expenses), 380.0)

    def test_negative_net_profit(self):
        revenue = [make_revenue(50)]
        expenses = [make_expense(120)]
        self.assertAlmostEqual(net_profit(revenue, expenses), -70.0)

    def test_zero_net_profit(self):
        revenue = [make_revenue(50)]
        expenses = [make_expense(50)]
        self.assertEqual(net_profit(revenue, expenses), 0.0)

    def test_both_empty(self):
        self.assertEqual(net_profit([], []), 0.0)


class TestProfitSummary(unittest.TestCase):

    def test_summary_fields(self):
        revenue = [make_revenue(300), make_revenue(200)]
        expenses = [make_expense(90), make_expense(10)]
        summary = profit_summary(revenue, expenses)
        self.assertEqual(
            set(summary.keys()),
            {"total_revenue", "total_expenses", "net_profit", "SIMULATED"},
        )
        self.assertAlmostEqual(summary["total_revenue"], 500.0)
        self.assertAlmostEqual(summary["total_expenses"], 100.0)
        self.assertAlmostEqual(summary["net_profit"], 400.0)
        self.assertIs(summary["SIMULATED"], True)


if __name__ == "__main__":
    unittest.main()
