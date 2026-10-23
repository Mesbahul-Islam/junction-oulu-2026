"""Community Notes on snippets and community posts (FR-4)."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel

# FR-4: fixed rating tag vocabulary; every rating carries ≥1 tag.
RATING_TAGS = [
    "clear_sources",
    "relevant",
    "unbiased",
    "important_context",
    "biased_language",
    "missing_sources",
    "outdated",
    "off_topic",
    "hard_to_understand",
]


def validate_citation_urls(value):
    if not isinstance(value, list) or not value:
        raise ValidationError("At least one citation URL is required.")
    check = URLValidator(schemes=["http", "https"])
    for url in value:
        check(url)


def validate_rating_tags(value):
    if not isinstance(value, list) or not value:
        raise ValidationError("At least one tag is required.")
    unknown = set(value) - set(RATING_TAGS)
    if unknown:
        raise ValidationError(f"Unknown tags: {sorted(unknown)}")


class CommunityNote(TimeStampedModel):
    class Status(models.TextChoices):
        NEEDS_MORE_RATINGS = "needs_more_ratings", "Needs more ratings"
        HELPFUL = "helpful", "Helpful"
        NOT_HELPFUL = "not_helpful", "Not helpful"

    snippet = models.ForeignKey(
        "feed.Snippet", null=True, blank=True, on_delete=models.CASCADE, related_name="community_notes"
    )
    post = models.ForeignKey(
        "communities.Post", null=True, blank=True, on_delete=models.CASCADE, related_name="community_notes"
    )
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="community_notes")
    claim_summary = models.CharField(max_length=500)
    context = models.TextField(max_length=2000)
    citation_urls = models.JSONField(default=list, validators=[validate_citation_urls])
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.NEEDS_MORE_RATINGS, db_index=True
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(snippet__isnull=False) & Q(post__isnull=True))
                | (Q(snippet__isnull=True) & Q(post__isnull=False)),
                name="note_targets_exactly_one",
            )
        ]

    def __str__(self):
        return self.claim_summary[:60]


class NoteRating(TimeStampedModel):
    class Value(models.TextChoices):
        HELPFUL = "helpful", "Helpful"
        SOMEWHAT_HELPFUL = "somewhat_helpful", "Somewhat helpful"
        NOT_HELPFUL = "not_helpful", "Not helpful"

    note = models.ForeignKey(CommunityNote, on_delete=models.CASCADE, related_name="ratings")
    rater = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="note_ratings")
    value = models.CharField(max_length=20, choices=Value.choices)
    tags = models.JSONField(default=list, validators=[validate_rating_tags])

    class Meta:
        constraints = [models.UniqueConstraint(fields=["note", "rater"], name="uniq_note_rater")]
