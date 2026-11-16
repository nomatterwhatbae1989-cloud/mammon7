import json
import unittest

from src.discovery import (DiscoveryError, Lead, discover, lead_from_dict,
                           make_lead, parse_remoteok, parse_remotive,
                           parse_weworkremotely)

REMOTEOK_SAMPLE = json.dumps([
    {"legal": "terms"},
    {"position": "Python Automation Script", "company": "Acme",
     "url": "https://remoteok.com/1", "description": "Scrape-free automation",
     "tags": ["python", "automation"], "date": "2026-01-01"},
    {"position": "", "company": "Bad", "url": "", "tags": []},
])

REMOTIVE_SAMPLE = json.dumps({"jobs": [
    {"title": "Data Entry Bot", "company_name": "Beta", "url": "https://x/1",
     "description": "clean data", "category": "python", "publication_date": "2026-01-02"},
    {"title": "", "url": "", "category": ""},
]})

WEWORK_SAMPLE = """<?xml version="1.0"?>
<rss><channel>
<item><title>Python Dev: Acme Corp</title><link>https://w/1</link>
<description>&lt;p&gt;Build&lt;/p&gt; tools</description><pubDate>Mon, 1 Jan 2026</pubDate></item>
<item><title></title><link></link></item>
</channel></rss>"""


class TestMakeLead(unittest.TestCase):

    def test_valid_lead(self):
        lead = make_lead("Script job", "Acme", "manual", "https://x/1",
                         "desc", ["Python", " API "])
        self.assertEqual(lead.title, "Script job")
        self.assertEqual(lead.tags, ["python", "api"])
        self.assertIs(lead.to_dict()["PUBLIC_SOURCE"], True)

    def test_missing_required_fields_rejected(self):
        for kwargs in ({"title": ""}, {"source": ""}, {"url": ""},
                       {"title": 42}):
            with self.subTest(**kwargs):
                with self.assertRaises(DiscoveryError):
                    make_lead(**{**dict(title="t", company="c", source="s",
                                        url="u"), **kwargs})

    def test_bad_tags_rejected(self):
        with self.assertRaises(DiscoveryError):
            make_lead("t", "c", "s", "u", tags="python")

    def test_lead_from_dict_roundtrip(self):
        lead = make_lead("T", "C", "manual", "https://x", "d", ["py"])
        rebuilt = lead_from_dict(lead.to_dict())
        self.assertEqual(rebuilt, lead)

    def test_lead_from_dict_missing_keys(self):
        with self.assertRaises(DiscoveryError):
            lead_from_dict({"title": "x"})


class TestParsers(unittest.TestCase):

    def test_remoteok_parser(self):
        items = parse_remoteok(REMOTEOK_SAMPLE)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Python Automation Script")
        self.assertEqual(items[0]["source"], "remoteok")

    def test_remoteok_invalid_json(self):
        with self.assertRaises(DiscoveryError):
            parse_remoteok("{not json")

    def test_remotive_parser(self):
        items = parse_remotive(REMOTIVE_SAMPLE)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "Data Entry Bot")
        self.assertEqual(items[0]["tags"], ["python"])

    def test_remotive_invalid(self):
        with self.assertRaises(DiscoveryError):
            parse_remotive('{"jobs": "nope"}')

    def test_wework_parser(self):
        items = parse_weworkremotely(WEWORK_SAMPLE)
        self.assertEqual(len(items), 1)
        self.assertIn("Build tools", items[0]["description"])
        self.assertEqual(items[0]["source"], "weworkremotely")

    def test_wework_invalid_xml(self):
        with self.assertRaises(DiscoveryError):
            parse_weworkremotely("<not-xml>")


class TestDiscover(unittest.TestCase):

    def test_discover_with_fake_fetch(self):
        def fake_fetch(url):
            if "remoteok" in url:
                return REMOTEOK_SAMPLE
            if "remotive" in url:
                return REMOTIVE_SAMPLE
            return WEWORK_SAMPLE

        leads = discover(fetch=fake_fetch)
        self.assertEqual(len(leads), 3)
        sources = {lead.source for lead in leads}
        self.assertEqual(sources, {"remoteok", "remotive", "weworkremotely"})

    def test_discover_skips_failing_sources(self):
        def fake_fetch(url):
            if "remoteok" in url:
                return REMOTEOK_SAMPLE
            raise ConnectionError("down")

        leads = discover(fetch=fake_fetch, sources=["remoteok", "remotive"])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].source, "remoteok")

    def test_discover_all_sources_fail(self):
        def fake_fetch(url):
            raise ConnectionError("offline")

        self.assertEqual(discover(fetch=fake_fetch), [])

    def test_discover_unknown_source(self):
        with self.assertRaises(DiscoveryError):
            discover(fetch=lambda u: "", sources=["madeup"])

    def test_discover_deduplicates_urls(self):
        def fake_fetch(url):
            return REMOTEOK_SAMPLE if "remoteok" in url else WEWORK_SAMPLE

        leads = discover(fetch=fake_fetch,
                         sources=["remoteok", "remoteok"])
        remoteok_leads = [l for l in leads if l.source == "remoteok"]
        self.assertEqual(len(remoteok_leads), 1)


if __name__ == "__main__":
    unittest.main()
