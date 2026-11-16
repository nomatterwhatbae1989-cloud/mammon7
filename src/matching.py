"""Skill matching and proposal drafting for discovered leads.

Scores are ESTIMATES. Proposals are drafts only — MAMMON never sends,
submits, or contacts anyone; the human always reviews and submits.
"""
from __future__ import annotations

from typing import Iterable, List

from .core import RevenueCore
from .discovery import Lead


class MatchingError(Exception):
    """Raised when matching or proposal inputs are invalid."""


def _normalize_skills(skills: Iterable[str]) -> List[str]:
    result = []
    for skill in skills:
        if not isinstance(skill, str) or not skill.strip():
            raise MatchingError("skills must be non-empty strings")
        result.append(skill.strip().lower())
    return result


def match_lead(lead: Lead, skills: Iterable[str],
               hourly_rate: float = 25.0) -> dict:
    """Score how well a lead fits a skills profile (0-100 ESTIMATE)."""
    if not isinstance(lead, Lead):
        raise MatchingError("expected a Lead")
    skills = _normalize_skills(skills)
    if not skills:
        raise MatchingError("skills profile cannot be empty")
    if not isinstance(hourly_rate, (int, float)) or isinstance(hourly_rate, bool) \
            or hourly_rate <= 0:
        raise MatchingError("hourly_rate must be a positive number")

    haystack = " ".join([lead.title, lead.description,
                         " ".join(lead.tags)]).lower()
    matched = [s for s in skills if s in haystack]
    lead_tags = set(lead.tags)
    for skill in skills:
        if skill in lead_tags and skill not in matched:
            matched.append(skill)

    coverage = len(matched) / len(skills)
    tag_bonus = len(lead_tags & set(skills)) * 10
    score = min(100.0, coverage * 70 + tag_bonus + 15)

    return {
        "lead_id": lead.id,
        "title": lead.title,
        "source": lead.source,
        "url": lead.url,
        "match_score": round(score, 1),
        "matched_skills": matched,
        "est_hours": max(2, round(20 - score / 5)),
        "est_bid": round(max(5.0, (20 - score / 5) * float(hourly_rate)), 2),
        "ESTIMATE": True,
    }


def rank_matches(lead_list: Iterable[Lead], skills: Iterable[str],
                 hourly_rate: float = 25.0) -> List[dict]:
    """Score and rank leads best-first (ESTIMATES)."""
    matches = [match_lead(lead, skills, hourly_rate) for lead in lead_list]
    matches.sort(key=lambda m: m["match_score"], reverse=True)
    return matches


def build_proposal(lead: Lead, skills: Iterable[str],
                   hourly_rate: float = 25.0,
                   pitch: str = "") -> dict:
    """Draft a tailored proposal for a lead. DRAFT ONLY — never sent."""
    if not isinstance(lead, Lead):
        raise MatchingError("expected a Lead")
    skills = _normalize_skills(skills)
    if not skills:
        raise MatchingError("skills profile cannot be empty")
    if not isinstance(pitch, str):
        raise MatchingError("pitch must be a string")

    match = match_lead(lead, skills, hourly_rate)
    matched = match["matched_skills"]

    return {
        "id": RevenueCore.gen_id(),
        "timestamp": RevenueCore.now_iso(),
        "lead_title": lead.title,
        "lead_url": lead.url,
        "lead_source": lead.source,
        "status": "DRAFT_NOT_SENT",
        "est_bid": match["est_bid"],
        "est_hours": match["est_hours"],
        "body": _proposal_text(lead, skills, matched, match, pitch),
        "ESTIMATE": True,
    }


def _proposal_text(lead, skills, matched, match, pitch) -> str:
    lines = [
        f"Subject: Proposal — {lead.title}",
        "",
        f"Hello,",
        "",
        f"I saw your posting \"{lead.title}\""
        + (f" at {lead.company}" if lead.company else "") + ".",
        "",
        "Relevant experience for this job:",
    ]
    if matched:
        for skill in matched:
            lines.append(f"- {skill}")
    else:
        lines.append("- General programming and automation experience")
    lines += [
        "",
        "How I would approach it:",
        "1. Confirm the exact scope and acceptance criteria with you.",
        "2. Deliver a working first version quickly for your review.",
        "3. Refine based on your feedback until it meets the requirements.",
        "",
        f"Estimated effort: about {match['est_hours']} hours.",
        f"Proposed fixed price: ${match['est_bid']:.2f} (estimate, negotiable).",
    ]
    if pitch.strip():
        lines += ["", pitch.strip()]
    lines += [
        "",
        "— Sent by [your name]",
        "",
        "DRAFT ONLY: review, personalize, and send it yourself.",
        "MAMMON did not contact anyone or submit anything.",
    ]
    return "\n".join(lines)
