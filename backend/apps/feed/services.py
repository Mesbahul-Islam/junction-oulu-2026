"""Feed business logic (FR-2.x, FR-3.9 language selection, FR-3.11 arrival sequence)."""

from django.apps import apps
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from apps.common.choices import Language, ReviewStatus

from .models import ArrivalBucket, Interaction, Snippet, SnippetReport, SnippetVersion

# FR-3.9: requester's preferred language first, then Finnish (source), then English.
FALLBACK_LANGUAGES = [Language.FINNISH, Language.ENGLISH]
VISIBLE_VERSION_STATUSES = [ReviewStatus.APPROVED, ReviewStatus.PUBLISHED]
CANDIDATE_WINDOW = 200  # newest N published snippets are ranked per request

ARRIVAL_BUCKET_ORDER = [ArrivalBucket.FIRST_48H, ArrivalBucket.FIRST_WEEK, ArrivalBucket.FIRST_MONTH]


def language_chain(preferred) -> list[str]:
    chain = [preferred] if preferred else []
    return chain + [lang for lang in FALLBACK_LANGUAGES if lang not in chain]


def requester_language(request) -> str:
    user = getattr(request, "user", None)
    explicit = request.query_params.get("lang") if hasattr(request, "query_params") else None
    if explicit:
        return explicit
    if user is not None and user.is_authenticated:
        return user.preferred_language
    return Language.FINNISH


def pick_version(versions, chain):
    """First approved version in the language chain, or None. `versions` is prefetched."""
    by_lang = {v.language: v for v in versions if v.review_status in VISIBLE_VERSION_STATUSES}
    for lang in chain:
        if lang in by_lang:
            return by_lang[lang]
    return None


def published_snippets(chain, now=None):
    """Published, non-expired snippets that have an approved version in one of `chain` languages."""
    now = now or timezone.now()
    approved_versions = SnippetVersion.objects.filter(
        language__in=chain, review_status__in=VISIBLE_VERSION_STATUSES
    ).select_related("approved_by")
    Note = apps.get_model("notes", "CommunityNote")
    return (
        Snippet.objects.filter(review_status=ReviewStatus.PUBLISHED)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gte=now))
        .filter(versions__language__in=chain, versions__review_status__in=VISIBLE_VERSION_STATUSES)
        .distinct()
        .select_related("community", "created_by_agent_run")
        .prefetch_related(
            Prefetch("versions", queryset=approved_versions),
            "source_documents",
            Prefetch("community_notes", queryset=Note.objects.filter(status="helpful")),
            "corrections",
        )
        .annotate(
            n_likes=Count("interactions", filter=Q(interactions__kind="like"), distinct=True),
            n_shares=Count("interactions", filter=Q(interactions__kind="share"), distinct=True),
            n_bookmarks=Count("interactions", filter=Q(interactions__kind="bookmark"), distinct=True),
            n_comments=Count("comments", distinct=True),
        )
    )


def feed_candidates(chain, *, community=None, tag=None):
    qs = published_snippets(chain)
    if community:
        qs = qs.filter(community_id=int(community)) if str(community).isdigit() else qs.filter(community__slug=community)
    if tag:
        # JSON `contains` is unsupported on SQLite; filter in Python there.
        from django.db import connection

        if connection.vendor == "postgresql":
            qs = qs.filter(tags__contains=[tag])
        else:
            return [s for s in qs.order_by("-published_at")[:CANDIDATE_WINDOW] if tag in (s.tags or [])]
    return list(qs.order_by("-published_at")[:CANDIDATE_WINDOW])


# --- FR-3.11 arrival sequence -------------------------------------------------


def arrival_bucket_for(days_since_arrival: int | None):
    if days_since_arrival is None or days_since_arrival < 0:
        return None
    if days_since_arrival < 2:
        return ArrivalBucket.FIRST_48H
    if days_since_arrival < 7:
        return ArrivalBucket.FIRST_WEEK
    if days_since_arrival < 30:
        return ArrivalBucket.FIRST_MONTH
    return None


def arrival_buckets_to_show(current) -> list[str]:
    """Current bucket first, then earlier buckets the newcomer may have missed."""
    if current is None:
        return []
    idx = ARRIVAL_BUCKET_ORDER.index(current)
    return [ARRIVAL_BUCKET_ORDER[idx]] + ARRIVAL_BUCKET_ORDER[:idx][::-1]


# --- interactions -----------------------------------------------------------

INTERACT_KINDS = {"like", "unlike", "bookmark", "unbookmark", "share", "expand", "read_through", "view"}


def interact(user, snippet, kind: str) -> dict:
    """Record an interaction. like/bookmark are idempotent toggles; unlike/unbookmark remove them."""
    if kind not in INTERACT_KINDS:
        raise ValueError(f"unknown interaction kind: {kind}")
    if kind in ("unlike", "unbookmark"):
        Interaction.objects.filter(user=user, snippet=snippet, kind=kind[2:]).delete()
        return {"kind": kind[2:], "active": False}
    if kind in Interaction.TOGGLE_KINDS:
        try:
            with transaction.atomic():
                Interaction.objects.get_or_create(user=user, snippet=snippet, kind=kind)
        except IntegrityError:
            pass
        return {"kind": kind, "active": True}
    Interaction.objects.create(user=user, snippet=snippet, kind=kind)
    return {"kind": kind, "active": True}


def report(user, snippet, reason, body="") -> SnippetReport:
    """FR-3.10: reader report → editorial reopen (top-priority review task)."""
    from apps.editorial import services as editorial

    rep = SnippetReport.objects.create(user=user, snippet=snippet, reason=reason, body=body)
    # TODO: threshold / rate-limit reports before unpublishing to resist abuse.
    editorial.reopen(snippet, reason="report")
    editorial.log(snippet, "reported", actor=user, payload={"report_id": rep.pk, "reason": reason})
    return rep


def build_comment_tree(comments) -> list[dict]:
    """Nest a flat, created_at-ordered comment list into threads."""
    nodes = {
        c.pk: {
            "id": c.pk,
            "user": getattr(c.user, "display_name", "") or str(c.user),
            "body": c.body,
            "created_at": c.created_at,
            "replies": [],
        }
        for c in comments
    }
    roots = []
    for c in comments:
        (nodes[c.parent_id]["replies"] if c.parent_id in nodes else roots).append(nodes[c.pk])
    return roots


# --- FR-3.13 AI disclosure ---------------------------------------------------


def agent_roles(snippet) -> list[str]:
    """Agents that touched this snippet (AgentStep.agent), in first-seen order."""
    AgentStep = apps.get_model("agents", "AgentStep")
    q = Q(snippet=snippet)
    if snippet.created_by_agent_run_id:
        q |= Q(run_id=snippet.created_by_agent_run_id)
    # TODO: batch this per page instead of one query per card.
    roles = AgentStep.objects.filter(q).order_by("created_at").values_list("agent", flat=True)
    return list(dict.fromkeys(roles))
