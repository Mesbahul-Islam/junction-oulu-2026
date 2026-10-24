"""Wire desk: fetch the Kaleva free-articles RSS feed and hand the news editor what is worth considering.

The feed URL is fixed in code (``KALEVA_FEED_URL``), not read from the database.
New or changed articles are stored as ``SourceDocument`` (duplicates skipped by content
hash; a changed article gets ``version + 1``). Candidates are the recent stored articles
no story was made from yet, minus opinion pieces and paid content (JSN clauses 11 and 16):
those are never rewritten as neutral news.
"""

from __future__ import annotations

import html
import logging
import re
from datetime import timedelta
from urllib.parse import urljoin

from django.apps import apps
from django.utils import timezone

from ..graph.text import clean_html, content_hash

logger = logging.getLogger(__name__)

KALEVA_FEED_URL = "https://www.kaleva.fi/feedit/rss/managed-listing/rss-maksuttomat/"
KALEVA_FEED_NAME = "Kaleva – Maksuttomat"
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


# --- pictures ----------------------------------------------------------------------------

_IMG_EXT = re.compile(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", re.I)
_META_TAG = re.compile(r"<meta\b[^>]*>", re.I)
_META_ATTR = re.compile(r'([\w:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\')')
_IMG_SRC = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']", re.I)
PAGE_IMAGE_TIMEOUT = 8


def _http_url(value, base: str = "") -> str:
    value = html.unescape(str(value or "")).strip()
    value = urljoin(base, value) if value else ""
    return value if value.startswith(("http://", "https://")) and len(value) <= 1500 else ""


def entry_image(e, base: str = "") -> str:
    """The picture an RSS entry itself carries: enclosure, media:content / media:thumbnail,
    else the first <img> in its HTML. "" if none."""
    for enc in e.get("enclosures", []):
        href = enc.get("href") or enc.get("url") or ""
        if str(enc.get("type", "")).startswith("image/") or _IMG_EXT.search(href):
            if url := _http_url(href, base):
                return url
    for key in ("media_content", "media_thumbnail"):
        for m in e.get(key, []) or []:
            kind = str(m.get("type", "")) or str(m.get("medium", ""))
            if (not kind or kind.startswith("image")) and (url := _http_url(m.get("url"), base)):
                return url
    raw = " ".join(c.get("value", "") for c in e.get("content", [])) + " " + (e.get("summary", "") or "")
    if m := _IMG_SRC.search(raw):
        return _http_url(m.group(1), base)
    return ""


def page_image(url: str) -> str:
    """The article page's og:image / twitter:image (the picture Kaleva shares for the story)."""
    import httpx

    try:
        resp = httpx.get(url, timeout=PAGE_IMAGE_TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except Exception as exc:
        logger.info("No picture from %s: %s", url, type(exc).__name__)
        return ""
    wanted = {"og:image:secure_url": 0, "og:image": 1, "twitter:image": 2, "twitter:image:src": 2}
    best: tuple[int, str] | None = None
    for tag in _META_TAG.findall(resp.text[:200_000]):
        attrs = {k.lower(): (a or b) for k, a, b in _META_ATTR.findall(tag)}
        name = (attrs.get("property") or attrs.get("name") or "").lower()
        if name in wanted and (image := _http_url(attrs.get("content"), str(resp.url))):
            if best is None or wanted[name] < best[0]:
                best = (wanted[name], image)
    return best[1] if best else ""


def fetch_entries(url: str) -> list[dict]:
    import feedparser
    import httpx

    resp = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()
    entries = []
    for e in feedparser.parse(resp.content).entries:
        body = " ".join(c.get("value", "") for c in e.get("content", [])) or e.get("summary", "") or e.get("description", "")
        link = e.get("link") or url
        entries.append({"url": link, "title": clean_html(e.get("title", "")), "body": clean_html(body),
                        "image_url": entry_image(e, link)})
    return entries


def store(entry: dict):
    """Save a new or changed article; None if we already have this exact content.

    The picture comes from the RSS entry, else from the article page. An article we already
    have but without a picture gets one now.
    """
    SourceDocument = apps.get_model("feed", "SourceDocument")
    title, body, url = entry["title"], entry["body"], entry["url"]
    if not (title or body):
        return None
    h = content_hash(title, body)
    seen = SourceDocument.objects.filter(content_hash=h)
    if seen.exists():
        if seen.filter(image_url="").exists() and (image := entry.get("image_url") or page_image(url)):
            seen.filter(image_url="").update(image_url=image)
        return None
    latest = SourceDocument.objects.filter(url=url).order_by("-version").first()
    return SourceDocument.objects.create(
        url=url, title=title[:500], body=body, publisher=KALEVA_FEED_NAME, fetched_at=timezone.now(),
        image_url=entry.get("image_url") or page_image(url),
        content_hash=h, version=(latest.version + 1) if latest else 1,
    )


def run_wire_desk(community) -> dict:
    """Fetch the Kaleva free-articles feed. Returns {"candidates": [docs], "report": {...}}.

    ``community`` is not used to pick the feed (it is the same for everyone); it is kept so
    the runner's call stays the same.
    """
    SourceDocument = apps.get_model("feed", "SourceDocument")
    fetched = new = 0
    errors = []
    try:
        entries = fetch_entries(KALEVA_FEED_URL)
    except Exception as exc:
        logger.warning("Wire desk could not fetch %s: %s", KALEVA_FEED_URL, exc)
        errors.append(f"{KALEVA_FEED_NAME}: {type(exc).__name__}")
    else:
        fetched = len(entries[:MAX_ENTRIES_PER_FEED])
        new = sum(1 for entry in entries[:MAX_ENTRIES_PER_FEED] if store(entry))

    recent = SourceDocument.objects.filter(
        publisher=KALEVA_FEED_NAME,
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
        "report": {"feed": KALEVA_FEED_URL, "fetched": fetched, "new": new, "candidates": len(candidates),
                   "excluded": excluded[:20], "excluded_count": len(excluded), "errors": errors},
    }
