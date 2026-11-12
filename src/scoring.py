"""Opportunity scoring for MAMMON-7.

All scores are ESTIMATES built from user-supplied inputs.
They are not verified market data and do not guarantee income.
"""
from __future__ import annotations

from .core import RevenueCore


class ScoringError(Exception):
    """Raised when an opportunity cannot be created or scored."""


class Opportunity:
    """A potential product or service, described by estimate factors."""

    __slots__ = ("id", "title", "kind", "est_demand", "competition",
                 "skills_required", "time_hours", "startup_cost",
                 "est_price", "est_delivery_cost", "created_at")

    def __init__(self, id, title, kind, est_demand, competition, skills_required,
                 time_hours, startup_cost, est_price, est_delivery_cost, created_at):
        self.id = id
        self.title = title
        self.kind = kind
        self.est_demand = est_demand
        self.competition = competition
        self.skills_required = skills_required
        self.time_hours = time_hours
        self.startup_cost = startup_cost
        self.est_price = est_price
        self.est_delivery_cost = est_delivery_cost
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "kind": self.kind,
            "est_demand": self.est_demand,
            "competition": self.competition,
            "skills_required": self.skills_required,
            "time_hours": self.time_hours,
            "startup_cost": self.startup_cost,
            "est_price": self.est_price,
            "est_delivery_cost": self.est_delivery_cost,
            "created_at": self.created_at,
            "ESTIMATE": True,
        }


def _validate_number(value, name: str, minimum: float, maximum: float) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ScoringError(f"{name} must be a number")
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise ScoringError(f"{name} must be finite")
    if value < minimum or value > maximum:
        raise ScoringError(f"{name} must be between {minimum} and {maximum}")
    return value


def create_opportunity(title, kind, est_demand, competition, skills_required,
                       time_hours, startup_cost, est_price, est_delivery_cost):
    """Create an Opportunity. Factor scales (1-10):
    est_demand: 10 = very high demand. competition: 10 = very crowded.
    skills_required: 10 = expert-level skills needed.
    """
    if not isinstance(title, str) or title.strip() == "":
        raise ScoringError("title must be a non-empty string")
    if not isinstance(kind, str) or kind.strip() == "":
        raise ScoringError("kind must be a non-empty string")
    est_demand = _validate_number(est_demand, "est_demand", 1, 10)
    competition = _validate_number(competition, "competition", 1, 10)
    skills_required = _validate_number(skills_required, "skills_required", 1, 10)
    time_hours = _validate_number(time_hours, "time_hours", 0, 10000)
    startup_cost = _validate_number(startup_cost, "startup_cost", 0, 10**9)
    est_price = _validate_number(est_price, "est_price", 0, 10**9)
    est_delivery_cost = _validate_number(est_delivery_cost, "est_delivery_cost", 0, 10**9)
    if est_delivery_cost > est_price:
        raise ScoringError("est_delivery_cost cannot exceed est_price")
    return Opportunity(
        id=RevenueCore.gen_id(),
        title=title.strip(),
        kind=kind.strip(),
        est_demand=est_demand,
        competition=competition,
        skills_required=skills_required,
        time_hours=time_hours,
        startup_cost=startup_cost,
        est_price=est_price,
        est_delivery_cost=est_delivery_cost,
        created_at=RevenueCore.now_iso(),
    )


def score_opportunity(opp: Opportunity) -> dict:
    """Score an opportunity. Higher total = more attractive.

    Weights favor high demand, low competition, low startup cost,
    low time, and realistic profit. Total is 0-100 (ESTIMATE).
    """
    if not isinstance(opp, Opportunity):
        raise ScoringError("expected an Opportunity")

    demand_score = opp.est_demand * 10.0                      # 10-100
    competition_score = (10 - opp.competition) * 10.0         # 0-90
    skills_score = (10 - opp.skills_required) * 5.0           # 0-45
    time_score = max(0.0, 100.0 - opp.time_hours * 2.0) / 2.0  # 0-50
    cost_score = max(0.0, 50.0 - opp.startup_cost)             # 0-50
    profit = opp.est_price - opp.est_delivery_cost
    profit_score = min(50.0, profit / 2.0)                     # 0-50

    raw = (demand_score + competition_score + skills_score
           + time_score + cost_score + profit_score)
    total = round(min(100.0, raw / 3.75), 1)  # normalize to 0-100

    return {
        "opportunity_id": opp.id,
        "title": opp.title,
        "est_profit_per_sale": round(profit, 2),
        "break_even_units": (int(-(-opp.startup_cost // profit))
                             if profit > 0 else None),
        "components": {
            "demand": round(demand_score, 1),
            "competition": round(competition_score, 1),
            "skills": round(skills_score, 1),
            "time": round(time_score, 1),
            "startup_cost": round(cost_score, 1),
            "profit": round(profit_score, 1),
        },
        "total": total,
        "ESTIMATE": True,
    }


def rank_opportunities(opportunities) -> list:
    """Rank opportunities by total score, highest first (ESTIMATES)."""
    scored = []
    for opp in opportunities:
        if not isinstance(opp, Opportunity):
            raise ScoringError("expected Opportunity objects")
        scored.append((score_opportunity(opp)["total"], opp))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [opp for _, opp in scored]
