"""Scout agent - newsroom role: **news scout / tip desk** (FR-3.1, FR-3.14).

Human counterpart (FR-3.6): community members and editors adding tips and
sources. The scout only *collects*: it fetches the community's active
``communities.SourceFeed`` rows, stores each new or changed item as a
``feed.SourceDocument`` (deduplicated by ``content_hash``; a changed item at a
known URL gets ``version + 1``), and pulls open ``CommunityContribution`` rows
as community signals. It also loads the community's glossary and context
library for the downstream agents.

When ``state["offline"]`` is true the scout never touches DB or network and
just passes through whatever ``raw_items`` / ``glossary`` / ``context_entries``
the caller supplied (tests, demos).
"""

from __future__ import annotations

import logging
from typing import Any

from apps.common.choices import SOURCE_LANGUAGE

from ..state import NewsroomState, RawItem
from ..text import clean_html, content_hash, truncate

logger = logging.getLogger(__name__)

MAX_ENTRIES_PER_FEED = 20
MAX_SIGNALS = 10
USER_AGENT = "JunctionOuluNewsroomBot/0.1 (+https://example.invalid/bot)"
SIGNAL_KINDS = ("question", "topic_suggestion", "tip", "bridge_story")


def scout(state: NewsroomState) -> dict[str, Any]:
    errors: list[dict] = []
    if state.get("offline"):
        raw = list(state.get("raw_items") or [])
        signals = [r for r in raw if r.get("kind") == "community_signal"]
        community = state.get("community") or {}
        return {
            "raw_items": raw,
            "signals": signals,
            "glossary": state.get("glossary") or [],
            "context_entries": state.get("context_entries") or [],
            "source_language": state.get("source_language") or SOURCE_LANGUAGE.value,
            "language_targets": _targets(state, community),
        }

    from django.apps import apps

    CommunityGroup = apps.get_model("communities", "CommunityGroup")
    community_obj = CommunityGroup.objects.get(pk=state["community_id"])
    community = {
        "id": community_obj.pk,
        "name": community_obj.name,
        "slug": getattr(community_obj, "slug", ""),
        "municipality": getattr(community_obj, "municipality", ""),
        "bbox": getattr(community_obj, "bbox", None),
        "languages": list(getattr(community_obj, "languages", None) or []),
    }

    raw_items: list[RawItem] = list(state.get("raw_items") or [])
    if state.get("source_ids"):
        raw_items += load_source_documents(state["source_ids"])
    elif state.get("fetch", True):
        raw_items += fetch_community_feeds(community_obj, errors)

    signals: list[RawItem] = []
    if not state.get("source_ids"):
        signals = load_signals(community_obj)
        raw_items += signals

    return {
        "community": community,
        "raw_items": raw_items,
        "signals": signals,
        "glossary": load_glossary(community_obj),
        "context_entries": load_context_entries(community_obj),
        "source_language": state.get("source_language") or SOURCE_LANGUAGE.value,
        "language_targets": _targets(state, community),
        "errors": list(state.get("errors") or []) + errors,
    }


def _targets(state: NewsroomState, community: dict) -> list[str]:
    src = state.get("source_language") or SOURCE_LANGUAGE.value
    targets = state.get("language_targets")
    if targets is None:
        targets = community.get("languages") or []
    out: list[str] = []
    for lang in targets:
        lang = str(lang)
        if lang != src and lang not in out:
            out.append(lang)
    return out


# ---------------------------------------------------------------------------
# DB / network helpers
# ---------------------------------------------------------------------------


def doc_to_item(doc) -> RawItem:
    return {
        "key": f"doc:{doc.pk}",
        "kind": "source",
        "source_document_id": doc.pk,
        "contribution_id": None,
        "url": doc.url or "",
        "title": doc.title or "",
        "body": doc.body or "",
        "publisher": getattr(doc, "publisher", "") or "",
        "fetched_at": doc.fetched_at.isoformat() if getattr(doc, "fetched_at", None) else "",
        "content_hash": doc.content_hash or "",
        "version": int(getattr(doc, "version", 1) or 1),
    }


def load_source_documents(source_ids: list[int]) -> list[RawItem]:
    from django.apps import apps

    SourceDocument = apps.get_model("feed", "SourceDocument")
    return [doc_to_item(d) for d in SourceDocument.objects.filter(pk__in=source_ids)]


def load_signals(community_obj) -> list[RawItem]:
    from django.apps import apps

    Contribution = apps.get_model("communities", "CommunityContribution")
    qs = (
        Contribution.objects.filter(community=community_obj, status="new", kind__in=SIGNAL_KINDS)
        .order_by("-occurrence_count", "-created_at")[:MAX_SIGNALS]
    )
    items: list[RawItem] = []
    for c in qs:
        body = c.body or ""
        items.append(
            {
                "key": f"signal:{c.pk}",
                "kind": "community_signal",
                "source_document_id": None,
                "contribution_id": c.pk,
                "url": "",
                "title": truncate(body, 90),
                "body": body,
                "publisher": "community",
                "fetched_at": c.created_at.isoformat() if getattr(c, "created_at", None) else "",
                "content_hash": content_hash("", body),
                "version": 0,
                "contribution_kind": c.kind,
                "occurrence_count": int(getattr(c, "occurrence_count", 1) or 1),
                "named_persons_consent": bool(getattr(c, "named_persons_consent", False)),
                "contributor_consent": bool(getattr(c, "contributor_consent", False)),
            }
        )
    return items


def load_glossary(community_obj) -> list[dict]:
    from django.apps import apps
    from django.db.models import Q

    GlossaryTerm = apps.get_model("communities", "GlossaryTerm")
    qs = GlossaryTerm.objects.filter(Q(community=community_obj) | Q(community__isnull=True))
    return [
        {"language": g.language, "term_fi": g.term_fi, "term": g.term, "note": getattr(g, "note", "") or ""}
        for g in qs
    ]


def load_context_entries(community_obj) -> list[dict]:
    from django.apps import apps
    from django.db.models import Q

    ContextEntry = apps.get_model("communities", "ContextEntry")
    from django.utils import timezone

    # FR-3.8: only reviewed, currently valid context-library entries.
    today = timezone.localdate()
    qs = ContextEntry.objects.filter(
        Q(community=community_obj) | Q(community__isnull=True),
        reviewed_at__isnull=False,
    ).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today))
    return [{"id": e.pk, "language": e.language, "topic": e.topic, "body": e.body} for e in qs]


def fetch_community_feeds(community_obj, errors: list) -> list[RawItem]:
    from django.apps import apps
    from django.utils import timezone

    SourceFeed = apps.get_model("communities", "SourceFeed")
    items: list[RawItem] = []
    for feed in SourceFeed.objects.filter(community=community_obj, is_active=True):
        try:
            entries = fetch_feed_entries(feed.url, feed.kind)
        except Exception as exc:
            logger.warning("Scout failed to fetch %s: %s", feed.url, exc)
            errors.append({"agent": "scout", "feed_id": feed.pk, "error": str(exc)[:300]})
            continue
        for entry in entries[:MAX_ENTRIES_PER_FEED]:
            doc = store_source_document(feed, entry)
            if doc is not None:
                items.append(doc_to_item(doc))
        feed.last_fetched_at = timezone.now()
        feed.save(update_fields=["last_fetched_at"])
    return items


def fetch_feed_entries(url: str, kind: str) -> list[dict]:
    """Return a list of ``{url, title, body}`` dicts for one feed."""
    import feedparser
    import httpx

    resp = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
    resp.raise_for_status()

    if kind == "rss":
        parsed = feedparser.parse(resp.content)
        out = []
        for e in parsed.entries:
            body = ""
            if e.get("content"):
                body = " ".join(c.get("value", "") for c in e["content"])
            body = clean_html(body or e.get("summary", "") or e.get("description", ""))
            link = e.get("link") or f"{url}#{e.get('id', e.get('title', ''))}"
            out.append({"url": link, "title": clean_html(e.get("title", "")), "body": body})
        return out

    if kind == "api":
        # TODO: per-source adapters. Accepts a JSON list of {title, url, body}.
        data = resp.json()
        if isinstance(data, dict):
            data = data.get("items") or data.get("results") or []
        return [
            {"url": d.get("url") or url, "title": str(d.get("title", "")), "body": clean_html(str(d.get("body", "")))}
            for d in data
            if isinstance(d, dict)
        ]

    # "html" / "council": treat the page as one document.
    # TODO: council-agenda parser (split agenda items into documents).
    import re

    text = resp.text
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    return [{"url": url, "title": clean_html(m.group(1)) if m else url, "body": truncate(clean_html(text), 8000)}]


def store_source_document(feed, entry: dict):
    """Create a SourceDocument for new/changed content; return None if unchanged."""
    from django.apps import apps
    from django.utils import timezone

    SourceDocument = apps.get_model("feed", "SourceDocument")
    title, body, url = entry.get("title", ""), entry.get("body", ""), entry.get("url", "")
    if not (title or body):
        return None
    h = content_hash(title, body)
    if SourceDocument.objects.filter(content_hash=h).exists():
        return None  # identical content already ingested (any feed)
    latest = SourceDocument.objects.filter(url=url).order_by("-version").first()
    version = (int(latest.version or 0) + 1) if latest else 1
    return SourceDocument.objects.create(
        url=url,
        title=title[:500],
        body=body,
        publisher=getattr(feed, "name", "") or "",
        fetched_at=timezone.now(),
        content_hash=h,
        version=version,
        source_feed=feed,
    )

