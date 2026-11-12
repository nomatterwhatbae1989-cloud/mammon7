import unittest

from src.fees import FeeEngine
from src.forecast import (ForecastError, monthly_summary,
                          project_from_records, scenario_model)
from src.refunds import RefundEngine
from src.revenue import RevenueEngine, RevenueRecord
from src.expenses import ExpenseEngine, ExpenseRecord


def make_revenue(amount, month="2026-01", service_id="svc"):
    record = RevenueEngine().create_record(service_id, amount)
    return record


def make_expense(amount, category="software"):
    return ExpenseEngine().create_record(category, amount)


class TestMonthlySummary(unittest.TestCase):

    def test_empty_summary(self):
        summary = monthly_summary()
        self.assertEqual(summary["months"], {})
        self.assertEqual(summary["basis"], "VERIFIED_RECORDS")

    def test_groups_by_month(self):
        r_jan = RevenueRecord(id="a" * 32, timestamp="2026-01-15T00:00:00.000Z",
                              service_id="svc", amount=100.0)
        r_feb = RevenueRecord(id="b" * 32, timestamp="2026-02-15T00:00:00.000Z",
                              service_id="svc", amount=50.0)
        e_jan = ExpenseRecord(id="c" * 32, timestamp="2026-01-20T00:00:00.000Z",
                              category="software", amount=20.0)
        summary = monthly_summary([r_jan, r_feb], [e_jan])
        self.assertEqual(set(summary["months"].keys()), {"2026-01", "2026-02"})
        self.assertAlmostEqual(summary["months"]["2026-01"]["revenue"], 100.0)
        self.assertAlmostEqual(summary["months"]["2026-01"]["expenses"], 20.0)
        self.assertAlmostEqual(summary["months"]["2026-01"]["net"], 80.0)
        self.assertAlmostEqual(summary["months"]["2026-02"]["net"], 50.0)

    def test_fees_and_refunds_reduce_net(self):
        from src.revenue import RevenueRecord
        from src.fees import FeeRecord
        from src.refunds import RefundRecord
        r = RevenueRecord(id="a" * 32, timestamp="2026-03-01T00:00:00.000Z",
                          service_id="svc", amount=200.0)
        f = FeeRecord(id="b" * 32, timestamp="2026-03-02T00:00:00.000Z",
                      revenue_id=r.id, amount=30.0)
        ref = RefundRecord(id="c" * 32, timestamp="2026-03-03T00:00:00.000Z",
                          revenue_id=r.id, amount=20.0, reason="test")
        summary = monthly_summary([r], fee_records=[f], refund_records=[ref])
        march = summary["months"]["2026-03"]
        self.assertAlmostEqual(march["fees"], 30.0)
        self.assertAlmostEqual(march["refunds"], 20.0)
        self.assertAlmostEqual(march["net"], 150.0)

    def test_rejects_bad_timestamp(self):
        from src.revenue import RevenueRecord
        bad = RevenueRecord(id="a" * 32, timestamp="garbage",
                           service_id="svc", amount=10.0)
        with self.assertRaises(ForecastError):
            monthly_summary([bad])

    def test_rejects_naive_timestamp(self):
        from src.revenue import RevenueRecord
        naive = RevenueRecord(id="a" * 32, timestamp="2026-03-01T00:00:00.000",
                             service_id="svc", amount=10.0)
        with self.assertRaises(ForecastError):
            monthly_summary([naive])

    def test_rejects_wrong_types(self):
        with self.assertRaises(ForecastError):
            monthly_summary(["nope"])


class TestProjectFromRecords(unittest.TestCase):

    def records_for_two_months(self):
        from src.revenue import RevenueRecord
        from src.expenses import ExpenseRecord
        return (
            [RevenueRecord(id="a" * 32, timestamp="2026-01-10T00:00:00.000Z",
                           service_id="svc", amount=100.0),
             RevenueRecord(id="b" * 32, timestamp="2026-02-10T00:00:00.000Z",
                           service_id="svc", amount=300.0)],
            [ExpenseRecord(id="c" * 32, timestamp="2026-01-10T00:00:00.000Z",
                           category="software", amount=50.0)],
        )

    def test_projection_uses_average(self):
        revenue, expenses = self.records_for_two_months()
        result = project_from_records(revenue, expenses, months_ahead=3)
        self.assertEqual(result["recorded_months"], 2)
        self.assertAlmostEqual(result["average_monthly_net"], 175.0)
        self.assertEqual(len(result["projected_months"]), 3)
        self.assertAlmostEqual(result["projected_total_net"], 525.0)
        self.assertIs(result["ESTIMATE"], True)

    def test_refuses_with_one_month(self):
        from src.revenue import RevenueRecord
        one = [RevenueRecord(id="a" * 32, timestamp="2026-01-10T00:00:00.000Z",
                             service_id="svc", amount=100.0)]
        with self.assertRaises(ForecastError):
            project_from_records(one)

    def test_refuses_with_no_records(self):
        with self.assertRaises(ForecastError):
            project_from_records([])

    def test_rejects_bad_months_ahead(self):
        revenue, expenses = self.records_for_two_months()
        for bad in (0, -1, 61, "6", True, 3.5):
            with self.subTest(months_ahead=bad):
                with self.assertRaises(ForecastError):
                    project_from_records(revenue, expenses, months_ahead=bad)


class TestScenarioModel(unittest.TestCase):

    def test_scenarios(self):
        result = scenario_model(500.0, months=12)
        self.assertAlmostEqual(result["conservative"], 3000.0)
        self.assertAlmostEqual(result["base"], 6000.0)
        self.assertAlmostEqual(result["optimistic"], 12000.0)
        self.assertIs(result["ESTIMATE"], True)

    def test_rejects_bad_average(self):
        for bad in (float("nan"), float("inf")):
            with self.subTest(value=bad):
                with self.assertRaises(ForecastError):
                    scenario_model(bad)

    def test_rejects_bad_multiplier(self):
        with self.assertRaises(ForecastError):
            scenario_model(100, conservative=-0.5)
        with self.assertRaises(ForecastError):
            scenario_model(100, base="1")

    def test_rejects_bad_months(self):
        for bad in (0, -3, "12", True):
            with self.subTest(months=bad):
                with self.assertRaises(ForecastError):
                    scenario_model(100, months=bad)


if __name__ == "__main__":
    unittest.main()
