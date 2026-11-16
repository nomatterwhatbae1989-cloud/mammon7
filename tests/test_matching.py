import unittest

from src.discovery import make_lead
from src.matching import (MatchingError, build_proposal, match_lead,
                          rank_matches)

SKILLS = ["python", "automation", "api"]


def make_test_lead(**overrides):
    fields = dict(
        title="Python automation script for data cleanup",
        company="Acme",
        source="manual",
        url="https://example.com/job/1",
        description="Need a Python script to automate API data cleanup.",
        tags=["python", "automation"],
    )
    fields.update(overrides)
    return make_lead(**fields)


class TestMatchLead(unittest.TestCase):

    def test_good_match_scores_high(self):
        match = match_lead(make_test_lead(), SKILLS)
        self.assertGreaterEqual(match["match_score"], 60.0)
        self.assertIn("python", match["matched_skills"])
        self.assertIs(match["ESTIMATE"], True)

    def test_poor_match_scores_lower(self):
        good = match_lead(make_test_lead(), SKILLS)["match_score"]
        bad = match_lead(make_test_lead(
            title="Graphic designer for logos",
            description="Design logos and brand art.",
            tags=["design"]), SKILLS)["match_score"]
        self.assertGreater(good, bad)

    def test_score_bounded(self):
        for lead in (make_test_lead(), make_test_lead(title="x", description="")):
            score = match_lead(lead, SKILLS)["match_score"]
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)

    def test_estimates_present(self):
        match = match_lead(make_test_lead(), SKILLS)
        self.assertGreater(match["est_hours"], 0)
        self.assertGreater(match["est_bid"], 0)

    def test_invalid_inputs(self):
        lead = make_test_lead()
        with self.assertRaises(MatchingError):
            match_lead(lead, [])
        with self.assertRaises(MatchingError):
            match_lead(lead, ["python"], hourly_rate=0)
        with self.assertRaises(MatchingError):
            match_lead(lead, ["python"], hourly_rate="25")
        with self.assertRaises(MatchingError):
            match_lead("not a lead", SKILLS)
        with self.assertRaises(MatchingError):
            match_lead(lead, ["", "python"])


class TestRankMatches(unittest.TestCase):

    def test_ranks_best_first(self):
        leads = [
            make_test_lead(),
            make_test_lead(title="Logo design", description="art",
                           tags=["design"]),
        ]
        ranked = rank_matches(leads, SKILLS)
        self.assertGreaterEqual(
            ranked[0]["match_score"], ranked[1]["match_score"])

    def test_empty_ok(self):
        self.assertEqual(rank_matches([], SKILLS), [])


class TestBuildProposal(unittest.TestCase):

    def test_proposal_draft(self):
        proposal = build_proposal(make_test_lead(), SKILLS)
        self.assertEqual(proposal["status"], "DRAFT_NOT_SENT")
        self.assertIs(proposal["ESTIMATE"], True)
        body = proposal["body"]
        self.assertIn("Subject: Proposal", body)
        self.assertIn("Python automation script", body)
        self.assertIn("python", body)
        self.assertIn("DRAFT ONLY", body)
        self.assertIn("MAMMON did not contact anyone", body)

    def test_proposal_includes_pitch(self):
        proposal = build_proposal(make_test_lead(), SKILLS,
                                   pitch="I built MAMMON-7.")
        self.assertIn("I built MAMMON-7.", proposal["body"])

    def test_proposal_no_match_still_drafted(self):
        proposal = build_proposal(
            make_test_lead(title="Chef", description="cooking", tags=[]),
            SKILLS)
        self.assertIn("General programming", proposal["body"])

    def test_invalid_inputs(self):
        with self.assertRaises(MatchingError):
            build_proposal(make_test_lead(), [])
        with self.assertRaises(MatchingError):
            build_proposal("nope", SKILLS)


if __name__ == "__main__":
    unittest.main()
