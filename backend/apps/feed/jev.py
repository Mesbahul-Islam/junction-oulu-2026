"""FR-2.3 personalised re-ranking with Jev (TypeSafe AI's System One model).

How it fits the feed (see docs/GUIDE.md §7):

1. `recommend.rank()` scores every candidate with the cheap heuristic formula.
2. The top `JEV_TOP_K` go to Jev: one request per (reader, snippet) pair, sent in
   parallel. Each request asks four atomic questions (below) about that pair.
3. `combine()` turns the answers into a 0–1 relevance score in code, so the weights
   stay ours to tune. The shortlist is re-sorted by a blend of Jev and heuristic.

Jev is optional and never blocks the feed: no API key, a timeout, an error or a
missing answer all fall back to the heuristic score for that snippet.

Privacy: Jev receives the reader's situation, language, days since arrival,
interest names and community/municipality names - never name, email, user id or
coordinates.
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, wait

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

# How each answer contributes to Jev's relevance score (sums to 1).
W_AFFECTS = 0.45
W_INTERESTS = 0.25
W_ACTION = 0.15
W_URGENCY = 0.15

URGENCY_LEVELS = [
    "Not time-sensitive for this reader",
    "Matters within the next month",
    "Matters within the next week",
    "Matters today or tomorrow",
]


def enabled() -> bool:
    return bool(settings.TYPESAFE_API_KEY) and settings.FEED_RANKER == "jev"


def questions() -> dict:
    """Atomic questions per (reader, snippet) pair; combined in `combine()`."""
    from typesafe_sdk import Noul, NoulCriteria, Score

    return {
        "affects_reader": Noul(
            instructions="Does this news directly affect this reader's daily life, rights, obligations, money, health or plans?",
            criteria=NoulCriteria(
                true="It changes something this reader, given their situation and area, must know or deal with",
                false="It is general news, about another place, or about people in a different situation",
            ),
        ),
        "matches_interests": Noul(
            instructions="Is this news about one of the reader's stated interests?",
        ),
        "needs_action": Noul(
            instructions="Should this reader do something because of this news?",
            criteria=NoulCriteria(
                true="There is a deadline, registration, application, changed service, or event this reader could act on",
                false="Nothing for this reader to do; it is purely informational",
            ),
        ),
        "urgency": Score(instructions="How time-sensitive is this news for this reader?", criteria=URGENCY_LEVELS),
    }


def combine(answers: dict) -> float:
    """Jev answers -> relevance in [0, 1]. `answers` holds floats keyed like `questions()`."""
    urgency = answers["urgency"] / (len(URGENCY_LEVELS) - 1)
    return (
        W_AFFECTS * answers["affects_reader"]
        + W_INTERESTS * answers["matches_interests"]
        + W_ACTION * answers["needs_action"]
        + W_URGENCY * urgency
    )


def reader_state(user) -> dict:
    """The reader half of the state: only coarse, non-identifying profile facts."""
    profile = getattr(user, "profile", None)
    interests, area = [], ""
    if profile is not None:
        interests = sorted(profile.interests.values_list("name", flat=True))
        if profile.location is not None:
            area = profile.location.municipality or profile.location.name
    Membership = apps.get_model("communities", "Membership")
    communities = sorted(Membership.objects.filter(user=user).values_list("community__name", flat=True))
    days = (timezone.localdate() - user.arrival_date).days if user.arrival_date else None
    return {
        "situation": user.reader_situation,
        "preferred_language": user.preferred_language,
        "days_since_arriving_in_finland": days,
        "interests": interests,
        "home_area": area,
        "communities": communities,
    }


def snippet_state(snippet, version) -> dict:
    return {
        "headline": version.headline,
        "summary": version.summary,
        "key_facts": version.key_facts or [],
        "topics": snippet.tags or [],
        "community": snippet.community.name if snippet.community_id else "region-wide",
        "risk_tier": snippet.risk_tier,
        "expires_at": snippet.expires_at.date().isoformat() if snippet.expires_at else None,
    }


def _cache_key(reader: dict, version) -> str:
    fingerprint = hashlib.sha1(json.dumps(reader, sort_keys=True).encode()).hexdigest()[:16]
    stamp = int(version.updated_at.timestamp()) if version.updated_at else 0
    return f"jev:{settings.JEV_MODEL}:{fingerprint}:{version.pk}:{stamp}"


def _ask(client, state: dict) -> dict:
    response = client.system_one(state=state, questions=questions())
    return {
        "affects_reader": response.nouls["affects_reader"].noul,
        "matches_interests": response.nouls["matches_interests"].noul,
        "needs_action": response.nouls["needs_action"].noul,
        "urgency": response.scores["urgency"].score,
    }


def make_client():
    from typesafe_sdk import RetryPolicy, TypeSafeClient

    return TypeSafeClient(
        api_key=settings.TYPESAFE_API_KEY,
        model=settings.JEV_MODEL,
        retry=RetryPolicy(max_retries=1, timeout=settings.JEV_TIMEOUT),
    )


def score_many(user, pairs) -> dict[int, dict]:
    """Ask Jev about each (snippet, version) pair for `user`.

    Returns {snippet_id: {"answers": {...}, "relevance": float}} for every pair that
    got an answer (from cache or Jev). Failed pairs are simply missing.
    """
    reader = reader_state(user)
    results, todo = {}, []
    for snippet, version in pairs:
        key = _cache_key(reader, version)
        cached = cache.get(key)
        if cached is not None:
            results[snippet.pk] = {"answers": cached, "relevance": combine(cached)}
        else:
            todo.append((snippet, key, {"reader": reader, "news": snippet_state(snippet, version)}))
    if not todo:
        return results

    try:
        client = make_client()
    except Exception:  # bad key, SDK problem: rank without Jev
        logger.exception("Could not create Jev client")
        return results
    pool = ThreadPoolExecutor(max_workers=settings.JEV_CONCURRENCY)
    with client:
        futures = {pool.submit(_ask, client, state): (snippet, key) for snippet, key, state in todo}
        done, not_done = wait(futures, timeout=settings.JEV_TIMEOUT * 2)
        # Don't let a slow call hold up the feed; stragglers are dropped.
        pool.shutdown(wait=False, cancel_futures=True)
        for future in done:
            snippet, key = futures[future]
            try:
                answers = future.result()
            except Exception as exc:
                logger.warning("Jev failed for snippet %s: %s", snippet.pk, exc)
                continue
            cache.set(key, answers, settings.JEV_CACHE_SECONDS)
            results[snippet.pk] = {"answers": answers, "relevance": combine(answers)}
    if not_done:
        logger.warning("Jev timed out for %d of %d snippets", len(not_done), len(todo))
    return results
