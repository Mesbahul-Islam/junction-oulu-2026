"""Wire desk: fetch the Kaleva RSS feeds and hand the news editor what is worth considering.

New or changed articles are stored as ``SourceDocument`` (duplicates skipped by content
hash; a changed article gets ``version + 1``). Candidates are the recent stored articles
no story was made from yet, minus opinion pieces and paid content (JSN clauses 11 and 16):
those are never rewritten as neutral news.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.apps import apps
from django.utils import timezone

from ..graph.text import clean_html, content_hash

logger = logging.getLogger(__name__)

USER_AGENT = "OuluNewsroomBot/1.0 (+hackathon prototype)"
MAX_ENTRIES_PER_FEED = 25
CANDIDATE_HOURS = 48
MAX_CANDIDATES = 120

# Kaleva and most outlets label reviews, columns and ads in the title, the lead or the URL.
COMMERCIAL_MARKERS = [r"kaupallinen yhteistyö", r"maksettu yhteistyö", r"sisältömarkkinointi", r"\bmainos\b",
                      r"sponsoroi", r"\bsponsored\b", r"\badvertorial", r"paid partnership"]
OPINION_MARKERS = [r"^arvio\s*:", r"/arvio-", r"kolumn", r"pääkirjoitu", r"mielipide", r"näkökulma\s*:",
                   r"^analyysi\s*:", r"lukijalta", r"vieraskynä", r"\bblogi", r"\bessee", r"\bcolumn(ist)?\b"]


def content_type(title: str, body: str = "", url: str = "") -> str:
    """"news", "opinion" or "commercial"."""
    title_low = (title or "").strip().lower()
    text = f"{title_low}\n{(body or '')[:400].lower()}\n{(url or '').lower()}"
    if any(re.search(p, text) for p in COMMERCIAL_MARKERS):
        return "commercial"
    if any(re.search(p, title_low if p.startswith("^") else text, re.M) for p in OPINION_MARKERS):
        return "opinion"
    return "news"


def fetch_entries(url: str) -> list[dict]:
    import feedparser
    import httpx

    resp = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    entries = []
    for e in feedparser.parse(resp.content).entries:
        body = " ".join(c.get("value", "") for c in e.get("content", [])) or e.get("summary", "") or e.get("description", "")
        entries.append({"url": e.get("link") or url, "title": clean_html(e.get("title", "")), "body": clean_html(body)})
    return entries


def store(feed, entry: dict):
    """Save a new or changed article; None if we already have this exact content."""
    SourceDocument = apps.get_model("feed", "SourceDocument")
    title, body, url = entry["title"], entry["body"], entry["url"]
    if not (title or body):
        return None
    h = content_hash(title, body)
    if SourceDocument.objects.filter(content_hash=h).exists():
        return None
    latest = SourceDocument.objects.filter(url=url).order_by("-version").first()
    return SourceDocument.objects.create(
        url=url, title=title[:500], body=body, publisher=feed.name, fetched_at=timezone.now(),
        content_hash=h, version=(latest.version + 1) if latest else 1, source_feed=feed,
    )


def run_wire_desk(community) -> dict:
    """Fetch every active feed of ``community``. Returns {"candidates": [docs], "report": {...}}."""
    SourceFeed = apps.get_model("communities", "SourceFeed")
    SourceDocument = apps.get_model("feed", "SourceDocument")
    feeds = list(SourceFeed.objects.filter(community=community, is_active=True))
    fetched = new = 0
    errors = []
    for feed in feeds:
        try:
            entries = fetch_entries(feed.url)
        except Exception as exc:
            logger.warning("Wire desk could not fetch %s: %s", feed.url, exc)
            errors.append(f"{feed.name}: {type(exc).__name__}")
            continue
        fetched += len(entries[:MAX_ENTRIES_PER_FEED])
        new += sum(1 for entry in entries[:MAX_ENTRIES_PER_FEED] if store(feed, entry))
        feed.last_fetched_at = timezone.now()
        feed.save(update_fields=["last_fetched_at"])

    recent = SourceDocument.objects.filter(
        source_feed__community=community,
        fetched_at__gte=timezone.now() - timedelta(hours=CANDIDATE_HOURS),
        snippets__isnull=True,
    ).order_by("-fetched_at")[:MAX_CANDIDATES]
    candidates, excluded = [], []
    for doc in recent:
        kind = content_type(doc.title, doc.body, doc.url)
        if kind == "news":
            candidates.append(doc)
        else:
            excluded.append({"title": doc.title[:120], "type": kind})
    return {
        "candidates": candidates,
        "report": {"feeds": len(feeds), "fetched": fetched, "new": new, "candidates": len(candidates),
                   "excluded": excluded[:20], "excluded_count": len(excluded), "errors": errors},
    }
