"""FR-4 Community Notes scoring (bridging-style, simplified).

A note is `helpful` (shown on the post as "Readers added context") only when (a) it
has ≥ MIN_RATINGS ratings, (b) the mean helpfulness score (helpful=1, somewhat=0.5,
not=0) ≥ HELPFUL_THRESHOLD and (c) the positive raters span ≥ MIN_PERSPECTIVES
perspective groups. `not_helpful` when the score ≤ NOT_HELPFUL_THRESHOLD. Otherwise
`needs_more_ratings`.

Perspective group = the rater's life situation (newcomer, student, seasonal worker,
resident): a note is shown only when people in different situations agree it helps,
so one group can't push its view on everyone. A shown note is then translated into
the community's languages (``tasks.translate_note``).
TODO: replace with matrix-factorization bridging (X/Twitter Community Notes) using
past rating agreement between raters.
"""

from django.apps import apps
from django.db import transaction

from .models import CommunityNote, NoteRating

MIN_RATINGS = 3
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
    """user_id → the rater's life situation (newcomer, student, seasonal_worker, resident)."""
    User = apps.get_model("accounts", "User")
    return dict(User.objects.filter(pk__in=user_ids).exclude(reader_situation="").values_list("pk", "reader_situation"))


def compute_status(note) -> str:
    """Recompute and persist note.status from its ratings."""
    rows = list(note.ratings.values_list("rater_id", "value"))
    groups = perspective_groups([uid for uid, _ in rows])
    new = status_from_ratings((value, groups.get(uid)) for uid, value in rows)
    if new != note.status:
        note.status = new
        note.save(update_fields=["status", "updated_at"])
        if new == Status.HELPFUL and note.post_id:
            from .tasks import translate_note

            transaction.on_commit(lambda: translate_note.delay(note.pk))
    return new


def create_note(*, author, post=None, snippet=None, **fields) -> CommunityNote:
    """A member proposes a note. On a community post, only members of that community may write."""
    from apps.agents.graph.text import guess_language

    if post is not None and not post.community.memberships.filter(user=author).exists():
        raise ValueError("Join this community to add notes to its posts.")
    note = CommunityNote(author=author, post=post, snippet=snippet, **fields)
    note.language = guess_language(f"{note.claim_summary} {note.context}")
    note.full_clean()
    note.save()
    return note


@transaction.atomic
def rate(note, user, value, tags) -> NoteRating:
    """Upsert a rating and recompute status (FR-4)."""
    if note.author_id == user.pk:
        raise ValueError("Authors cannot rate their own note.")
    rating, _ = NoteRating.objects.update_or_create(note=note, rater=user, defaults={"value": value, "tags": tags})
    compute_status(note)
    return rating
