"""FR-2.3 feed ranking: score(snippet, user) =
    W_INTEREST   * interest-vector overlap with snippet tags
  + W_GEO        * geo relevance (community membership / location in bbox)
  + W_ENGAGEMENT * engagement signal (read-through rate, expands, likes in a recent window)
  + W_FRESHNESS  * time decay since publication

Pure helpers are kept free of ORM access so they are unit-testable; `rank()`
batch-loads the context for a candidate window to avoid per-snippet queries.
TODO: replace interest overlap with embedding similarity (Snippet.embedding vs user vector).
"""

import math
from dataclasses import dataclass, field
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from . import jev

W_INTEREST = 0.40
W_GEO = 0.25
W_ENGAGEMENT = 0.20
W_FRESHNESS = 0.15

ENGAGEMENT_WINDOW = timedelta(days=7)
FRESHNESS_HALF_LIFE_HOURS = 48.0
MEMBER_GEO_SCORE = 1.0
BBOX_GEO_SCORE = 0.7
GLOBAL_GEO_SCORE = 0.3  # snippet without community/bbox (region-wide news)


@dataclass
class UserContext:
    interest_vector: dict = field(default_factory=dict)
    community_ids: set = field(default_factory=set)
    point: tuple | None = None  # (lng, lat)


@dataclass
class EngagementStats:
    views: int = 0
    read_throughs: int = 0
    expands: int = 0
    likes: int = 0


# --- pure helpers -----------------------------------------------------------


def interest_overlap(tags, interest_vector) -> float:
    """Mean user weight over the snippet's tags, clamped to [0, 1]."""
    if not tags or not interest_vector:
        return 0.0
    total = sum(float(interest_vector.get(t, 0.0)) for t in tags)
    return max(0.0, min(1.0, total / len(tags)))


def point_in_bbox(point, bbox) -> bool:
    if not point or not bbox or len(bbox) != 4:
        return False
    lng, lat = point
    min_lng, min_lat, max_lng, max_lat = bbox
    return min_lng <= lng <= max_lng and min_lat <= lat <= max_lat


def geo_relevance(community_id, bboxes, ctx: UserContext) -> float:
    """Member of snippet's community > user location inside snippet/community bbox > global."""
    if community_id is not None and community_id in ctx.community_ids:
        return MEMBER_GEO_SCORE
    if any(point_in_bbox(ctx.point, b) for b in bboxes if b):
        return BBOX_GEO_SCORE
    if community_id is None and not any(bboxes):
        return GLOBAL_GEO_SCORE
    return 0.0


def engagement_signal(stats: EngagementStats) -> float:
    """Read-through rate dominates; expand taps and likes saturate logarithmically."""
    rt_rate = stats.read_throughs / stats.views if stats.views else 0.0
    expands = math.log1p(stats.expands) / math.log1p(50)
    likes = math.log1p(stats.likes) / math.log1p(100)
    return max(0.0, min(1.0, 0.5 * min(1.0, rt_rate) + 0.25 * min(1.0, expands) + 0.25 * min(1.0, likes)))


def time_decay(age_hours: float, half_life: float = FRESHNESS_HALF_LIFE_HOURS) -> float:
    return 0.5 ** (max(0.0, age_hours) / half_life)


def combine(interest: float, geo: float, engagement: float, freshness: float) -> float:
    return W_INTEREST * interest + W_GEO * geo + W_ENGAGEMENT * engagement + W_FRESHNESS * freshness


# --- ORM-backed -------------------------------------------------------------


def user_context(user) -> UserContext:
    ctx = UserContext()
    if not user or not user.is_authenticated:
        return ctx
    profile = getattr(user, "profile", None)
    if profile is not None:
        ctx.interest_vector = profile.interest_vector or {}
        loc = profile.location
        if loc is not None and loc.lat is not None and loc.lng is not None:
            ctx.point = (loc.lng, loc.lat)
    Membership = apps.get_model("communities", "Membership")
    ctx.community_ids = set(Membership.objects.filter(user=user).values_list("community_id", flat=True))
    return ctx


def engagement_stats(snippet_ids, since=None) -> dict:
    from .models import Interaction

    since = since or timezone.now() - ENGAGEMENT_WINDOW
    stats = {sid: EngagementStats() for sid in snippet_ids}
    rows = (
        Interaction.objects.filter(snippet_id__in=snippet_ids, created_at__gte=since)
        .values("snippet_id", "kind")
        .annotate(n=Count("id"))
    )
    attr = {"view": "views", "read_through": "read_throughs", "expand": "expands", "like": "likes"}
    for r in rows:
        if r["kind"] in attr:
            setattr(stats[r["snippet_id"]], attr[r["kind"]], r["n"])
    return stats


def score(snippet, user, *, ctx: UserContext | None = None, stats: EngagementStats | None = None, now=None) -> float:
    """FR-2.3 relevance score for one snippet."""
    ctx = ctx if ctx is not None else user_context(user)
    stats = stats if stats is not None else engagement_stats([snippet.pk]).get(snippet.pk, EngagementStats())
    now = now or timezone.now()
    community_bbox = getattr(snippet.community, "bbox", None) if snippet.community_id else None
    ts = snippet.published_at or snippet.created_at or now
    return combine(
        interest_overlap(snippet.tags, ctx.interest_vector),
        geo_relevance(snippet.community_id, [snippet.geo_bbox, community_bbox], ctx),
        engagement_signal(stats),
        time_decay((now - ts).total_seconds() / 3600),
    )


def rank(snippets, user, chain=None) -> list:
    """Sort a candidate window by score (desc). Expects community select_related.

    When Jev is enabled and the user is signed in, the top JEV_TOP_K are re-ranked
    by Jev (see jev.py); everything below the shortlist keeps its heuristic order.
    Each snippet gets a `ranking` attribute explaining its position (shown on the card).
    """
    snippets = list(snippets)
    ctx = user_context(user)
    stats = engagement_stats([s.pk for s in snippets])
    now = timezone.now()
    scored = [(score(s, user, ctx=ctx, stats=stats[s.pk], now=now), s) for s in snippets]
    scored.sort(key=lambda p: p[0], reverse=True)
    for value, s in scored:
        s.ranking = {"ranker": "heuristic", "score": round(value, 4)}

    if jev.enabled() and user is not None and user.is_authenticated and chain:
        scored = _rerank_with_jev(scored, user, chain)
    return [s for _, s in scored]


def _rerank_with_jev(scored, user, chain):
    from .services import pick_version

    k = settings.JEV_TOP_K
    shortlist, rest = scored[:k], scored[k:]
    pairs = [(s, v) for _, s in shortlist if (v := pick_version(s.versions.all(), chain))]
    results = jev.score_many(user, pairs)
    w = settings.JEV_WEIGHT
    reranked = []
    for value, s in shortlist:
        if s.pk in results:
            r = results[s.pk]
            value = w * r["relevance"] + (1 - w) * value
            s.ranking = {
                "ranker": "jev",
                "score": round(value, 4),
                "jev_relevance": round(r["relevance"], 4),
                "jev": {k: round(v, 3) for k, v in r["answers"].items()},
            }
        reranked.append((value, s))
    reranked.sort(key=lambda p: p[0], reverse=True)
    return reranked + rest
