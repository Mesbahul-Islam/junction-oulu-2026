"""Assignment agent - newsroom role: **assignment desk / news editor's daily plan** (FR-3.2, FR-3.7).

Human counterpart (FR-3.6): the news editor approving the daily plan.
Ranks the scouted items by relevance to the community's readers: local stories,
topics its members chose as interests, freshness, and reader questions/tips (which
also boost matching official sources). Risk never affects which stories are picked, picks the top ``max_items``, and
proposes for each: >= 1 ``ReaderNeed``, a ``RiskTier`` and an expiry /
review-by date. The LLM proposal is never allowed to go *below* the keyword
heuristic's risk tier (safety floor); without an LLM the heuristic alone is
used.
"""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from apps.common.choices import ReaderNeed, RiskTier

from ..llm import structured_call
from ..schemas import AssignmentProposal
from ..state import Candidate, NewsroomState
from ..text import heuristic_reader_needs, heuristic_risk, is_first_week_topic, max_risk, tokens, topic_tags, truncate

DEFAULT_MAX_ITEMS = 8
SIGNAL_BOOST = 1.0
SIGNAL_MATCH_BOOST = 0.8
LOCAL_BOOST = 1.0
INTEREST_BOOST = 1.0
FRESH_BOOST = 0.5
VALID_NEEDS = {n.value for n in ReaderNeed}

# (expires_after, review_after) per tier
EXPIRY_RULES = {
    RiskTier.HIGH.value: (timedelta(days=30), timedelta(days=7)),
    RiskTier.MEDIUM.value: (timedelta(days=14), timedelta(days=7)),
    RiskTier.LOW.value: (timedelta(days=2), timedelta(days=1)),
}
_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_STOP = {"että", "joka", "jotka", "mutta", "kanssa", "sekä", "tämä", "with", "this", "that", "from", "have"}


def _significant(text: str) -> set[str]:
    return {t for t in tokens(text) if len(t) >= 5 and t not in _STOP and not t.isdigit()}


def _default_max_items() -> int:
    try:
        from django.conf import settings

        return int(getattr(settings, "AGENT_MAX_ITEMS", DEFAULT_MAX_ITEMS))
    except Exception:  # settings not configured (pure tests)
        return DEFAULT_MAX_ITEMS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def future_event_date(text: str, now: datetime) -> date | None:
    """First dd.mm.yyyy date in the text that lies in the future (<= 90 days)."""
    for d, m, y in _DATE_RE.findall(text or ""):
        try:
            dt = date(int(y), int(m), int(d))
        except ValueError:
            continue
        if now.date() <= dt <= (now + timedelta(days=90)).date():
            return dt
    return None


def compute_expiry(risk_tier: str, text: str, now: datetime | None = None) -> tuple[str, str]:
    now = now or _now()
    expires_after, review_after = EXPIRY_RULES.get(risk_tier, EXPIRY_RULES[RiskTier.MEDIUM.value])
    expires = now + expires_after
    review_by = now + review_after
    if risk_tier != RiskTier.HIGH.value:
        event = future_event_date(text, now)
        if event:
            expires = datetime.combine(event + timedelta(days=1), time(0, 0), tzinfo=timezone.utc)
            review_by = min(review_by, expires)
    return expires.isoformat(), review_by.isoformat()


def is_local(item: dict, community: dict) -> bool:
    """The story names the community's town, or came from a feed named after it (e.g. "Oulun seutu")."""
    stems = {_stem(community.get("municipality", "")), _stem(community.get("name", ""))} - {""}
    text = f"{item.get('title', '')} {item.get('body', '')} {item.get('publisher', '')}".lower()
    return any(stem in text for stem in stems)


def _stem(name: str) -> str:
    # "Oulu" also matches "Oulun", "oululainen"; very short names are skipped to avoid noise.
    name = (name or "").strip().lower()
    return name if len(name) >= 3 else ""


def audience_match(text: str, audience: dict[str, float]) -> float:
    """Share of the community's readers interested in this story's topics (0-1)."""
    return max((audience.get(tag, 0.0) for tag in topic_tags(text)), default=0.0)


def rank(raw_items: list[dict], now: datetime | None = None, community: dict | None = None,
         audience: dict[str, float] | None = None) -> list[Candidate]:
    """Order candidate stories by relevance to this community's readers (never by risk tier).

    score = 1 + local (1.0) + audience interest share (0-1) + fresh < 24 h (0.5)
              + 0.8 per reader question/tip it answers
    """
    now = now or _now()
    community, audience = community or {}, audience or {}
    sources = [r for r in raw_items if r.get("kind") != "community_signal"]
    signals = [r for r in raw_items if r.get("kind") == "community_signal"]
    sig_tokens = {s["key"]: _significant(s.get("body", "")) for s in signals}
    matched_signals: set[str] = set()

    cands: list[Candidate] = []
    for item in sources:
        text = f"{item.get('title', '')} {item.get('body', '')}"
        score = 1.0
        if is_local(item, community):
            score += LOCAL_BOOST
        score += INTEREST_BOOST * audience_match(text, audience)
        fetched = _parse_iso(item.get("fetched_at", ""))
        if fetched and now - fetched < timedelta(hours=24):
            score += FRESH_BOOST
        item_tokens = _significant(text)
        boosted_by = []
        for skey, stoks in sig_tokens.items():
            if stoks and len(item_tokens & stoks) >= 2:
                boosted_by.append(skey)
                matched_signals.add(skey)
        score += SIGNAL_MATCH_BOOST * len(boosted_by)
        cands.append({"key": item["key"], "score": round(score, 3), "boosted_by": boosted_by})

    for sig in signals:
        if sig["key"] in matched_signals:
            continue  # answered by an official source story instead
        occ = min(int(sig.get("occurrence_count") or 1), 10)
        # Reader questions/tips come from the community itself, so they count as local.
        score = 1.0 + LOCAL_BOOST + SIGNAL_BOOST + 0.2 * occ + INTEREST_BOOST * audience_match(sig.get("body", ""), audience)
        cands.append({"key": sig["key"], "score": round(score, 3), "boosted_by": []})

    cands.sort(key=lambda c: c["score"], reverse=True)
    return cands


def assignment(state: NewsroomState) -> dict[str, Any]:
    errors: list[dict] = []
    raw = {r["key"]: r for r in state.get("raw_items") or []}
    max_items = int(state.get("max_items") or _default_max_items())
    # JSN clauses 11 and 16: only news becomes a snippet. Opinion (columns, editorials,
    # reviews) and commercial content are excluded, never rewritten as neutral facts.
    excluded = [
        {"key": k, "title": r.get("title", "")[:120], "content_type": r["content_type"], "marker": r.get("content_marker", "")}
        for k, r in raw.items() if r.get("content_type", "news") != "news"
    ]
    news = [r for r in raw.values() if r.get("content_type", "news") == "news"]
    ranked = rank(news, community=state.get("community"), audience=state.get("audience_interests"))
    now = _now()

    assignments: dict[str, dict] = {}
    for cand in ranked:
        if len(assignments) >= max_items:
            break
        item = raw[cand["key"]]
        text = f"{item.get('title', '')}\n{item.get('body', '')}"
        is_signal = item.get("kind") == "community_signal"
        h_tier, hits = heuristic_risk(text)
        h_needs = heuristic_reader_needs(text, h_tier, is_signal, item.get("contribution_kind", ""))

        def fallback(h_tier=h_tier, h_needs=h_needs, hits=hits):
            return AssignmentProposal(
                reader_needs=h_needs,
                risk_tier=h_tier,
                rationale=f"keyword heuristic: {', '.join(hits[:3]) or 'no keywords, default medium'}",
            )

        prompt = (
            "Classify this local news item for a Finnish community newsroom.\n"
            "risk_tier: high = residence permits, health, employment, legal, safety; "
            "medium = transport, services, events; low = opening hours, weather.\n"
            "reader_needs: choose 1-3 of information, understanding, usefulness, emotion, break, community.\n"
            "content_type: news, or opinion (column, editorial, review, analysis), or commercial (advertising, "
            "sponsored or paid content).\n\n"
            f"TITLE: {item.get('title', '')}\nTEXT: {truncate(item.get('body', ''), 3000)}"
        )
        proposal = structured_call(prompt, AssignmentProposal, fallback, errors=errors, agent="assignment")
        if proposal.content_type.strip().lower() in ("opinion", "commercial"):  # the model can only exclude, never include
            excluded.append({"key": cand["key"], "title": item.get("title", "")[:120],
                             "content_type": proposal.content_type.strip().lower(), "marker": "model"})
            continue

        risk = max_risk(proposal.risk_tier, h_tier)
        needs = [n for n in proposal.reader_needs if n in VALID_NEEDS] or h_needs or [ReaderNeed.INFORMATION.value]
        expires_at, review_by = compute_expiry(risk, text, now)
        risk_source = "heuristic" if proposal.rationale.startswith("keyword heuristic") else (
            "llm" if risk == proposal.risk_tier else "llm+heuristic_floor"
        )
        assignments[cand["key"]] = {
            "reader_needs": needs,
            "risk_tier": risk,
            "risk_source": risk_source,
            "expires_at": expires_at,
            "review_by": review_by,
            "arrival_day_bucket": "first_week" if is_first_week_topic(text) else None,
            "rationale": proposal.rationale,
            "answers_signals": cand.get("boosted_by", []),
        }

    return {
        "excluded": excluded,
        "candidates": ranked,
        "assignments": assignments,
        "errors": list(state.get("errors") or []) + errors,
    }
