"""News editor desk: Jev decides which fetched articles the newsroom covers.

Jev (TypeSafe AI's System One) gets the community's readership (town, situations, interests,
languages: shares only, nothing about any person) and one article, and answers four atomic
questions. ``combine()`` turns them into a 0-1 score in code. Without a Jev key, or when
Jev fails for an article, a simple heuristic (local, fresh, readers' topics) scores it.
"""

from __future__ import annotations

import hashlib
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from ..graph.text import topic_tags, truncate

logger = logging.getLogger(__name__)

# How each Jev answer counts towards the article's score (sums to 1).
W_LOCAL, W_AFFECTS, W_USEFUL, W_NEWS = 0.30, 0.30, 0.15, 0.25
NEWSWORTHINESS = [
    "Trivial, gossip or pure entertainment",
    "Mildly interesting to some readers",
    "Important to many readers",
    "Very important to most readers",
]


def jev_enabled() -> bool:
    return bool(settings.TYPESAFE_API_KEY)


def audience(community) -> dict:
    """Who reads this community's news, as shares (no individual data)."""
    Membership = apps.get_model("communities", "Membership")
    Profile = apps.get_model("accounts", "Profile")
    members = Membership.objects.filter(community=community).select_related("user")
    users = [m.user for m in members]
    n = max(len(users), 1)
    situations = Counter(u.reader_situation for u in users if u.reader_situation)
    languages = Counter(u.preferred_language for u in users if u.preferred_language)
    interests = Counter(Profile.objects.filter(user__in=users).values_list("interests__name", flat=True))
    interests.pop(None, None)
    return {
        "town": community.municipality or community.name,
        "reader_situations": {k: round(v / n, 2) for k, v in situations.most_common()},
        "reader_languages": [k for k, _ in languages.most_common()],
        "top_interests": [k for k, _ in interests.most_common(8)],
    }


def _questions():
    from typesafe_sdk import Noul, NoulCriteria, Score

    return {
        "local": Noul(
            instructions="Is this news about the readers' town or its region?",
            criteria=NoulCriteria(true="It happens in or directly concerns the town or its region",
                                  false="It is about another place, or national or world news with no local angle"),
        ),
        "affects_readers": Noul(
            instructions="Does it affect the daily life, money, services, safety or plans of people living in the town, "
                         "including newcomers, students and seasonal workers?",
        ),
        "useful": Noul(
            instructions="Can a reader act on it?",
            criteria=NoulCriteria(true="An event, deadline, changed service, opening, warning or similar",
                                  false="Purely informational"),
        ),
        "newsworthy": Score(instructions="How newsworthy is it for these readers?", criteria=NEWSWORTHINESS),
    }


def combine(a: dict) -> float:
    return round(W_LOCAL * a["local"] + W_AFFECTS * a["affects_readers"] + W_USEFUL * a["useful"]
                 + W_NEWS * a["newsworthy"] / (len(NEWSWORTHINESS) - 1), 3)


def _ask(client, state: dict) -> dict:
    r = client.system_one(state=state, questions=_questions())
    return {"local": r.nouls["local"].noul, "affects_readers": r.nouls["affects_readers"].noul,
            "useful": r.nouls["useful"].noul, "newsworthy": r.scores["newsworthy"].score}


def jev_scores(docs, readers: dict) -> dict[int, dict]:
    """{doc pk: answers} for every article Jev answered (cached per article + readership)."""
    from apps.feed.jev import make_client

    fingerprint = hashlib.sha1(repr(sorted(readers.items())).encode()).hexdigest()[:12]
    out, todo = {}, []
    for doc in docs:
        key = f"newsroom-jev:1:{fingerprint}:{doc.content_hash}"
        cached = cache.get(key)
        if cached is not None:
            out[doc.pk] = cached
        else:
            state = {"readers": readers, "news": {"title": doc.title, "text": truncate(doc.body, 700),
                                                  "section": doc.publisher}}
            todo.append((doc, key, state))
    if not todo:
        return out
    try:
        client = make_client()
    except Exception:
        logger.exception("Could not create Jev client")
        return out
    pool = ThreadPoolExecutor(max_workers=settings.JEV_CONCURRENCY)
    with client:
        futures = {pool.submit(_ask, client, state): (doc, key) for doc, key, state in todo}
        done, not_done = wait(futures, timeout=max(20.0, settings.JEV_TIMEOUT * 4))
        pool.shutdown(wait=False, cancel_futures=True)
        for future in done:
            doc, key = futures[future]
            try:
                answers = future.result()
            except Exception as exc:
                logger.warning("Jev failed for article %s: %s", doc.pk, exc)
                continue
            cache.set(key, answers, settings.JEV_CACHE_SECONDS)
            out[doc.pk] = answers
    if not_done:
        logger.warning("Jev timed out for %d of %d articles", len(not_done), len(todo))
    return out


def heuristic(doc, readers: dict) -> tuple[float, list[str]]:
    """Fallback score: local, fresh, and on a topic the readers follow."""
    text = f"{doc.title} {doc.body} {doc.publisher}".lower()
    town = (readers.get("town") or "").lower()
    score, why = 0.2, []
    if town and town[:4] in text:
        score += 0.4
        why.append(f"about {readers['town']}")
    if doc.fetched_at and timezone.now() - doc.fetched_at < timedelta(hours=24):
        score += 0.2
        why.append("fresh")
    followed = {i.lower() for i in readers.get("top_interests", [])}
    topics = [t for t in topic_tags(f"{doc.title} {doc.body}") if t.replace("_", " ") in followed]
    if topics:
        score += 0.2
        why.append("readers follow " + ", ".join(topics[:2]))
    return round(score, 3), why


def rank(docs, community) -> list[dict]:
    """Every candidate scored, best first: [{doc, score, ranked_by, reasons}]."""
    readers = audience(community)
    answers = jev_scores(docs, readers) if jev_enabled() else {}
    ranked = []
    for doc in docs:
        a = answers.get(doc.pk)
        if a is not None:
            why = [w for w, yes in (("local", a["local"] >= 0.5), ("affects readers", a["affects_readers"] >= 0.5),
                                    ("readers can act on it", a["useful"] >= 0.5)) if yes]
            why.append(f"newsworthiness {a['newsworthy']:.1f} of {len(NEWSWORTHINESS) - 1}")
            ranked.append({"doc": doc, "score": combine(a), "ranked_by": "jev", "reasons": why})
        else:
            score, why = heuristic(doc, readers)
            ranked.append({"doc": doc, "score": score, "ranked_by": "heuristic", "reasons": why})
    ranked.sort(key=lambda r: (r["score"], r["doc"].fetched_at or timezone.now()), reverse=True)
    return ranked
