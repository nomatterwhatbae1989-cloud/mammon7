import unittest

from src.scoring import (Opportunity, ScoringError, create_opportunity,
                         rank_opportunities, score_opportunity)


def make_opp(**overrides):
    fields = dict(
        title="Spreadsheet budget tool",
        kind="digital-product",
        est_demand=7,
        competition=5,
        skills_required=3,
        time_hours=20,
        startup_cost=0,
        est_price=25,
        est_delivery_cost=2,
    )
    fields.update(overrides)
    return create_opportunity(**fields)


class TestCreateOpportunity(unittest.TestCase):

    def test_create_valid(self):
        opp = make_opp()
        self.assertEqual(opp.title, "Spreadsheet budget tool")
        self.assertEqual(len(opp.id), 32)
        self.assertTrue(opp.created_at.endswith("Z"))
        self.assertIs(opp.to_dict()["ESTIMATE"], True)

    def test_blank_title_rejected(self):
        for bad in ("", "   ", 42, None):
            with self.subTest(title=bad):
                with self.assertRaises(ScoringError):
                    make_opp(title=bad)

    def test_blank_kind_rejected(self):
        with self.assertRaises(ScoringError):
            make_opp(kind="")

    def test_out_of_range_factors_rejected(self):
        for name in ("est_demand", "competition", "skills_required"):
            for bad in (0, 11, -1, "5", True, float("nan")):
                with self.subTest(factor=name, value=bad):
                    with self.assertRaises(ScoringError):
                        make_opp(**{name: bad})

    def test_negative_costs_rejected(self):
        for name in ("startup_cost", "est_price", "est_delivery_cost", "time_hours"):
            with self.subTest(factor=name):
                with self.assertRaises(ScoringError):
                    make_opp(**{name: -5})

    def test_delivery_cost_above_price_rejected(self):
        with self.assertRaises(ScoringError):
            make_opp(est_price=10, est_delivery_cost=20)


class TestScoring(unittest.TestCase):

    def test_score_returns_estimate_flag(self):
        score = score_opportunity(make_opp())
        self.assertIs(score["ESTIMATE"], True)
        self.assertEqual(set(score.keys()),
                         {"opportunity_id", "title", "est_profit_per_sale",
                          "break_even_units", "components", "total", "ESTIMATE"})

    def test_total_within_bounds(self):
        for demand, comp in ((1, 10), (10, 1), (5, 5)):
            with self.subTest(demand=demand, competition=comp):
                score = score_opportunity(make_opp(est_demand=demand, competition=comp))
                self.assertGreaterEqual(score["total"], 0.0)
                self.assertLessEqual(score["total"], 100.0)

    def test_higher_demand_scores_higher(self):
        low = score_opportunity(make_opp(est_demand=3))["total"]
        high = score_opportunity(make_opp(est_demand=9))["total"]
        self.assertGreater(high, low)

    def test_less_competition_scores_higher(self):
        low = score_opportunity(make_opp(competition=9))["total"]
        high = score_opportunity(make_opp(competition=2))["total"]
        self.assertGreater(high, low)

    def test_zero_startup_cost_needs_no_break_even(self):
        score = score_opportunity(make_opp(startup_cost=0, est_price=25,
                                           est_delivery_cost=5))
        self.assertEqual(score["break_even_units"], 0)

    def test_break_even_units(self):
        score = score_opportunity(make_opp(startup_cost=100, est_price=25,
                                           est_delivery_cost=5))
        self.assertEqual(score["est_profit_per_sale"], 20.0)
        self.assertEqual(score["break_even_units"], 5)

    def test_no_profit_means_no_break_even(self):
        score = score_opportunity(make_opp(startup_cost=100, est_price=10,
                                           est_delivery_cost=10))
        self.assertIsNone(score["break_even_units"])

    def test_rejects_non_opportunity(self):
        with self.assertRaises(ScoringError):
            score_opportunity("not an opportunity")


class TestRanking(unittest.TestCase):

    def test_ranks_highest_first(self):
        strong = make_opp(title="strong", est_demand=9, competition=2)
        weak = make_opp(title="weak", est_demand=2, competition=9)
        ranked = rank_opportunities([weak, strong])
        self.assertEqual([o.title for o in ranked], ["strong", "weak"])

    def test_empty_list_ok(self):
        self.assertEqual(rank_opportunities([]), [])

    def test_rejects_non_opportunity(self):
        with self.assertRaises(ScoringError):
            rank_opportunities(["nope"])


if __name__ == "__main__":
    unittest.main()
