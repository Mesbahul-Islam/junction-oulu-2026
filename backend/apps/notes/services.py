"""FR-4 Community Notes scoring (bridging-style, simplified).

A note is `helpful` only when (a) it has ≥ MIN_RATINGS ratings, (b) the mean
helpfulness score (helpful=1, somewhat=0.5, not=0) ≥ HELPFUL_THRESHOLD and (c) the
positive raters span ≥ MIN_PERSPECTIVES distinct perspective groups. `not_helpful`
when the score ≤ NOT_HELPFUL_THRESHOLD. Otherwise `needs_more_ratings`.

Perspective group ≈ the rater's primary (earliest) community membership; raters
without any membership do not count towards (c), which keeps the rule conservative.
TODO: replace with matrix-factorization bridging (X/Twitter Community Notes) using
past rating agreement between raters.
"""

from django.apps import apps
from django.db import transaction

from .models import CommunityNote, NoteRating

MIN_RATINGS = 5
HELPFUL_THRESHOLD = 0.7
NOT_HELPFUL_THRESHOLD = 0.3
MIN_PERSPECTIVES = 2
VALUE_WEIGHT = {"helpful": 1.0, "somewhat_helpful": 0.5, "not_helpful": 0.0}

Status = CommunityNote.Status


def status_from_ratings(ratings) -> str:
    """Pure rule. `ratings` = iterable of (value, perspective_group_or_None)."""
    ratings = list(ratings)
    if len(ratings) < MIN_RATINGS:
        return Status.NEEDS_MORE_RATINGS
    score = sum(VALUE_WEIGHT[v] for v, _ in ratings) / len(ratings)
    if score <= NOT_HELPFUL_THRESHOLD:
        return Status.NOT_HELPFUL
    positive_groups = {g for v, g in ratings if VALUE_WEIGHT[v] > 0 and g is not None}
    if score >= HELPFUL_THRESHOLD and len(positive_groups) >= MIN_PERSPECTIVES:
        return Status.HELPFUL
    return Status.NEEDS_MORE_RATINGS


def perspective_groups(user_ids) -> dict:
    """user_id → primary community id (earliest membership), or absent."""
    Membership = apps.get_model("communities", "Membership")
    groups = {}
    for uid, cid in (
        Membership.objects.filter(user_id__in=user_ids).order_by("created_at").values_list("user_id", "community_id")
    ):
        groups.setdefault(uid, cid)
    return groups


def compute_status(note) -> str:
    """Recompute and persist note.status from its ratings."""
    rows = list(note.ratings.values_list("rater_id", "value"))
    groups = perspective_groups([uid for uid, _ in rows])
    new = status_from_ratings((value, groups.get(uid)) for uid, value in rows)
    if new != note.status:
        note.status = new
        note.save(update_fields=["status", "updated_at"])
    return new


@transaction.atomic
def rate(note, user, value, tags) -> NoteRating:
    """Upsert a rating and recompute status (FR-4)."""
    if note.author_id == user.pk:
        raise ValueError("Authors cannot rate their own note.")
    rating, _ = NoteRating.objects.update_or_create(note=note, rater=user, defaults={"value": value, "tags": tags})
    compute_status(note)
    return rating
