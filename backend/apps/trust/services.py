"""Trust score and levels. All numbers are in POINTS and the LEVEL thresholds below."""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.apps import apps
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from .models import MemberTrust

POINTS = {
    "helpful_note": 10,        # note rated helpful by raters in different situations (the notes cross-check)
    "unhelpful_note": -4,
    "accepted_contribution": 6,  # question or tip accepted or answered by editors
    "contribution_in_story": 6,  # ...and it became a published story
    "story_candidate": 3,      # a question other members asked too
    "approved_photo": 1,       # photo a moderator approved: the check is about blurring, not quality
    "like": 1,                 # likes from other members, at most LIKES_PER_POST per post
    "good_rating": 1,          # note ratings that matched the note's final verdict, at most RATING_CAP
    "removed_post": -15,       # post removed by a moderator
}
LIKES_PER_POST = 5
RATING_CAP = 10
CONTRIBUTOR_SCORE = 15
ELIGIBLE_SCORE = 50
ELIGIBLE_VERIFIED = 2      # helpful notes + accepted questions and tips
CLEAN_DAYS = 90            # no removed post in this many days
PAUSE_SCORE = 35           # a trusted voice below this is paused


def _models():
    get = apps.get_model
    return (get("communities", "Post"), get("communities", "PostLike"), get("communities", "CommunityContribution"),
            get("notes", "CommunityNote"), get("notes", "NoteRating"))


def signals_for(user, community) -> dict:
    """{signal: count} for one member in one community."""
    Post, PostLike, Contribution, Note, Rating = _models()
    note_scope = Q(snippet__community=community) | Q(post__community=community)
    notes = Note.objects.filter(note_scope, author=user)
    out = defaultdict(int)
    out["helpful_note"] = notes.filter(status="helpful").count()
    out["unhelpful_note"] = notes.filter(status="not_helpful").count()

    contribs = Contribution.objects.filter(author=user, community=community)
    out["accepted_contribution"] = contribs.filter(status__in=["accepted", "answered"]).count()
    out["contribution_in_story"] = contribs.filter(linked_snippet__review_status="published").count()
    out["story_candidate"] = contribs.filter(is_story_candidate=True).count()

    posts = Post.objects.filter(author=user, community=community)
    per_post = (PostLike.objects.filter(post__in=posts.exclude(status="removed")).exclude(user=user)
                .values("post").annotate(n=Count("user", distinct=True)))
    out["like"] = sum(min(row["n"], LIKES_PER_POST) for row in per_post)
    out["removed_post"] = posts.filter(status="removed").count()
    out["approved_photo"] = posts.filter(image_status="approved").exclude(status="removed").count()

    decided = Rating.objects.filter(rater=user, note__in=Note.objects.filter(note_scope, status__in=["helpful", "not_helpful"]))
    agree = sum(1 for value, verdict in decided.values_list("value", "note__status")
                if (value == "helpful" and verdict == "helpful") or (value == "not_helpful" and verdict == "not_helpful"))
    out["good_rating"] = min(agree, RATING_CAP)
    return dict(out)


def level_for(score: int, verified: int, recently_removed: bool, current: MemberTrust | None) -> str:
    L = MemberTrust.Level
    if current and current.level in (L.TRUSTED, L.PAUSED) and current.approved_at:
        # Approved before: stays trusted while it holds, pauses (not lost) when it doesn't.
        return L.PAUSED if (recently_removed or score < PAUSE_SCORE) else L.TRUSTED
    if score >= ELIGIBLE_SCORE and verified >= ELIGIBLE_VERIFIED and not recently_removed:
        return L.ELIGIBLE
    return L.CONTRIBUTOR if score >= CONTRIBUTOR_SCORE else L.MEMBER


def refresh(user, community) -> MemberTrust:
    Post = apps.get_model("communities", "Post")
    counts = signals_for(user, community)
    breakdown = {k: {"count": v, "points": v * POINTS[k]} for k, v in counts.items() if v}
    score = sum(b["points"] for b in breakdown.values())
    verified = counts.get("helpful_note", 0) + counts.get("accepted_contribution", 0)
    recently_removed = Post.objects.filter(author=user, community=community, status="removed",
                                           moderated_at__gte=timezone.now() - timedelta(days=CLEAN_DAYS)).exists()
    with transaction.atomic():
        trust, _ = MemberTrust.objects.select_for_update().get_or_create(user=user, community=community)
        trust.score, trust.verified, trust.breakdown = score, verified, breakdown
        trust.level = level_for(score, verified, recently_removed, trust)
        trust.save()
    return trust


def refresh_all() -> int:
    """Every member of every community (management command and tests)."""
    Membership = apps.get_model("communities", "Membership")
    n = 0
    for m in Membership.objects.select_related("user", "community"):
        refresh(m.user, m.community)
        n += 1
    return n


def next_step(trust: MemberTrust) -> dict:
    """What this member still needs for the next level."""
    L = MemberTrust.Level
    if trust.level == L.MEMBER:
        return {"level": L.CONTRIBUTOR, "points": CONTRIBUTOR_SCORE - trust.score}
    if trust.level == L.CONTRIBUTOR:
        return {"level": L.ELIGIBLE, "points": max(0, ELIGIBLE_SCORE - trust.score),
                "verified": max(0, ELIGIBLE_VERIFIED - trust.verified)}
    return {}


def can_decide(user, community) -> bool:
    from apps.common.permissions import has_role

    return bool(user and user.is_authenticated and (user.is_staff or has_role(user, "community_editor", community=community)
                                                     or has_role(user, "admin")))


def decide(trust: MemberTrust, editor, approve: bool, note: str = "") -> MemberTrust:
    """A person decides. Only eligible members can be approved."""
    L = MemberTrust.Level
    if approve and trust.level != L.ELIGIBLE:
        raise ValueError("Only eligible members can be approved")
    now = timezone.now()
    if approve:
        trust.level, trust.approved_by, trust.approved_at, trust.declined_at = L.TRUSTED, editor, now, None
    else:
        trust.declined_at, trust.approved_at, trust.approved_by = now, None, None
        if trust.level in (L.TRUSTED, L.PAUSED):
            trust.level = L.ELIGIBLE if trust.score >= ELIGIBLE_SCORE else L.CONTRIBUTOR
    trust.decision_note = note[:300]
    trust.save()
    return trust
