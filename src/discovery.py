"""Freelance lead discovery from public, bot-friendly sources.

Live mode pulls public job feeds (RemoteOK JSON API, Remotive JSON API,
WeWorkRemotely RSS). Offline mode accepts manually imported leads.
Sources that fail are skipped, never fatal. No logins, no scraping
behind rules, no personal data collected.
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Callable, Iterable, List, Optional

from .core import RevenueCore

REMOTEOK_URL = "https://remoteok.com/api"
REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
WEWORK_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

USER_AGENT = "MAMMON7-Lead-Discovery/1.0 (+public feeds only)"


class DiscoveryError(Exception):
    """Raised when lead data cannot be parsed or imported."""


class Lead:
    """A freelance lead discovered from a public source or manual import."""

    __slots__ = ("id", "timestamp", "title", "company", "source", "url",
                 "description", "tags", "published_at")

    def __init__(self, id, timestamp, title, company, source, url,
                 description, tags, published_at):
        self.id = id
        self.timestamp = timestamp
        self.title = title
        self.company = company
        self.source = source
        self.url = url
        self.description = description
        self.tags = tags
        self.published_at = published_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "title": self.title,
            "company": self.company,
            "source": self.source,
            "url": self.url,
            "description": self.description,
            "tags": list(self.tags),
            "published_at": self.published_at,
            "PUBLIC_SOURCE": True,
        }

    def __eq__(self, other):
        if not isinstance(other, Lead):
            return NotImplemented
        return self.to_dict() == other.to_dict()


def make_lead(title, company, source, url, description="", tags=None,
              published_at=""):
    """Create a validated Lead record."""
    if not isinstance(title, str) or title.strip() == "":
        raise DiscoveryError("title must be a non-empty string")
    if not isinstance(source, str) or source.strip() == "":
        raise DiscoveryError("source must be a non-empty string")
    if not isinstance(url, str) or url.strip() == "":
        raise DiscoveryError("url must be a non-empty string")
    if not isinstance(company, str):
        raise DiscoveryError("company must be a string")
    if not isinstance(description, str):
        raise DiscoveryError("description must be a string")
    if tags is None:
        tags = []
    if not isinstance(tags, (list, tuple)) or not all(
            isinstance(t, str) for t in tags):
        raise DiscoveryError("tags must be a list of strings")
    if published_at is not None and not isinstance(published_at, str):
        raise DiscoveryError("published_at must be a string or empty")
    return Lead(
        id=RevenueCore.gen_id(),
        timestamp=RevenueCore.now_iso(),
        title=title.strip(),
        company=company.strip(),
        source=source.strip(),
        url=url.strip(),
        description=description.strip()[:2000],
        tags=[t.strip().lower() for t in tags if t.strip()],
        published_at=published_at or "",
    )


def lead_from_dict(data: dict) -> Lead:
    """Rebuild a Lead from a serialized dict (offline import / reload)."""
    if not isinstance(data, dict):
        raise DiscoveryError("lead data must be a dict")
    missing = {"title", "source", "url"} - set(data.keys())
    if missing:
        raise DiscoveryError(f"lead missing keys: {sorted(missing)}")
    lead = make_lead(
        data["title"], data.get("company", ""), data["source"],
        data["url"], data.get("description", ""), data.get("tags", []),
        data.get("published_at", ""),
    )
    if isinstance(data.get("id"), str) and data["id"].strip():
        lead.id = data["id"]
    if isinstance(data.get("timestamp"), str) and data["timestamp"].strip():
        lead.timestamp = data["timestamp"]
    return lead


def parse_remoteok(text: str) -> List[dict]:
    """Parse RemoteOK's public JSON feed into lead dicts."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise DiscoveryError(f"invalid RemoteOK JSON: {exc}") from exc
    if not isinstance(data, list):
        raise DiscoveryError("RemoteOK feed did not return a list")
    leads = []
    for item in data:
        if not isinstance(item, dict) or "position" not in item:
            continue  # first item is legal/branding metadata
        leads.append({
            "title": str(item.get("position", "")).strip(),
            "company": str(item.get("company", "")).strip(),
            "source": "remoteok",
            "url": str(item.get("url", "")).strip(),
            "description": str(item.get("description", "") or "")[:2000],
            "tags": [str(t).lower() for t in (item.get("tags") or [])],
            "published_at": str(item.get("date", "") or ""),
        })
    return [l for l in leads if l["title"] and l["url"]]


def parse_remotive(text: str) -> List[dict]:
    """Parse Remotive's public JSON feed into lead dicts."""
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise DiscoveryError(f"invalid Remotive JSON: {exc}") from exc
    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        raise DiscoveryError("Remotive feed missing 'jobs' list")
    leads = []
    for item in jobs:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title", "")).strip()
        url = str(item.get("url", "")).strip()
        if not title or not url:
            continue
        leads.append({
            "title": title,
            "company": str(item.get("company_name", "")).strip(),
            "source": "remotive",
            "url": url,
            "description": str(item.get("description", "") or "")[:2000],
            "tags": [str(c).lower() for c in (item.get("category") or [])]
                    if isinstance(item.get("category"), list)
                    else [str(item.get("category", "")).lower()],
            "published_at": str(item.get("publication_date", "") or ""),
        })
    return leads


def parse_weworkremotely(text: str) -> List[dict]:
    """Parse WeWorkRemotely's public RSS feed into lead dicts."""
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise DiscoveryError(f"invalid WeWorkRemotely XML: {exc}") from exc
    leads = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        description = (item.findtext("description") or "")
        description = re.sub(r"<[^>]+>", " ", description)
        description = re.sub(r"\s+", " ", description)
        pub = (item.findtext("pubDate") or "").strip()
        company = ""
        if "—" in title or ":" in title:
            company = re.split(r"[:—]", title, 1)[1].strip() if ":" in title else ""
        leads.append({
            "title": title.split(":")[0].strip() if ":" in title else title,
            "company": company,
            "source": "weworkremotely",
            "url": link,
            "description": description.strip()[:2000],
            "tags": [],
            "published_at": pub,
        })
    return leads


PARSERS = {
    "remoteok": (REMOTEOK_URL, parse_remoteok),
    "remotive": (REMOTIVE_URL, parse_remotive),
    "weworkremotely": (WEWORK_URL, parse_weworkremotely),
}


def _default_fetch(url: str) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", "replace")


def discover(fetch: Optional[Callable[[str], str]] = None,
             sources: Optional[Iterable[str]] = None) -> List[Lead]:
    """Pull leads from public sources. Failing sources are skipped.

    fetch: injectable URL->text callable (used by tests). Defaults to
    a real HTTP GET.
    """
    fetch = fetch or _default_fetch
    if sources is None:
        sources = list(PARSERS)
    leads: List[Lead] = []
    for name in sources:
        if name not in PARSERS:
            raise DiscoveryError(f"unknown source: {name!r}")
        url, parser = PARSERS[name]
        try:
            text = fetch(url)
            items = parser(text)
        except Exception:
            continue  # source down or malformed: skip, never fatal
        for item in items:
            try:
                leads.append(make_lead(**item))
            except DiscoveryError:
                continue
    seen_urls = set()
    unique = []
    for lead in leads:
        if lead.url not in seen_urls:
            seen_urls.add(lead.url)
            unique.append(lead)
    return unique
