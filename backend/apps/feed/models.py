"""Feed: source documents, language-neutral snippets, per-language versions and
reader interactions (FR-2.x, FR-3.9 storage, FR-3.10 reports, FR-3.11 arrival buckets)."""

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.common.choices import Language, ReaderNeed, ReviewStatus, RiskTier  # noqa: F401 (ReaderNeed documents reader_needs)
from apps.common.models import TimeStampedModel


class SourceDocument(TimeStampedModel):
    """Raw ingested item (RSS entry, council minutes, web page). Versioned by content hash."""

    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    publisher = models.CharField(max_length=200, blank=True)
    # Lead picture of the article (from the RSS entry, else the article page's og:image). Hotlinked, not copied.
    image_url = models.URLField(max_length=1500, blank=True)
    # The article's full text from its page (the RSS body is only a teaser); read by the brief desk.
    full_text = models.TextField(blank=True)
    fetched_at = models.DateTimeField(null=True, blank=True)
    content_hash = models.CharField(max_length=64, db_index=True)
    version = models.PositiveIntegerField(default=1)
    source_feed = models.ForeignKey(
        "communities.SourceFeed", null=True, blank=True, on_delete=models.SET_NULL, related_name="documents"
    )

    class Meta:
        ordering = ["-fetched_at"]
        constraints = [models.UniqueConstraint(fields=["url", "version"], name="uniq_sourcedoc_url_version")]

    def __str__(self):
        return self.title or self.url


class ArrivalBucket(models.TextChoices):
    """FR-3.11: arrival-sequence buckets for newcomers."""

    FIRST_48H = "first_48h", "First 48 hours"
    FIRST_WEEK = "first_week", "First week"
    FIRST_MONTH = "first_month", "First month"


class Snippet(TimeStampedModel):
    """Language-neutral story record; text lives in SnippetVersion (FR-3.9)."""

    community = models.ForeignKey(
        "communities.CommunityGroup", null=True, blank=True, on_delete=models.CASCADE, related_name="snippets"
    )
    source_documents = models.ManyToManyField(SourceDocument, blank=True, related_name="snippets")
    tags = models.JSONField(default=list, blank=True)  # interest slugs
    reader_needs = models.JSONField(default=list, blank=True)  # ReaderNeed values
    risk_tier = models.CharField(max_length=10, choices=RiskTier.choices, default=RiskTier.MEDIUM)
    review_status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT, db_index=True
    )
    confidence = models.FloatField(default=0.0)  # 0..1, from agent pipeline
    embedding = models.JSONField(default=list, blank=True)
    geo_bbox = models.JSONField(null=True, blank=True)  # [min_lng, min_lat, max_lng, max_lat]
    image = models.ImageField(upload_to="snippets/%Y/%m/", null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    review_by = models.DateTimeField(null=True, blank=True)  # date the facts must be re-checked
    arrival_day_bucket = models.CharField(max_length=20, choices=ArrivalBucket.choices, null=True, blank=True)
    ai_generated = models.BooleanField(default=True)
    # The newsroom's verdict for the human editors: "ready" = every check passed and nothing
    # sensitive, one click to publish; "needs_review" = an editor must read it (see review_reasons).
    review_level = models.CharField(
        max_length=20, choices=[("ready", "Ready to send"), ("needs_review", "Needs review")], blank=True, db_index=True
    )
    review_reasons = models.JSONField(default=list, blank=True)
    created_by_agent_run = models.ForeignKey(
        "agents.AgentRun", null=True, blank=True, on_delete=models.SET_NULL, related_name="snippets"
    )

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        v = self.versions.filter(language=Language.FINNISH).first()
        return v.headline if v else f"Snippet #{self.pk}"


class SnippetVersion(TimeStampedModel):
    """Per-language text of a snippet (FR-3.9). Sámi versions must not be machine translated."""

    snippet = models.ForeignKey(Snippet, on_delete=models.CASCADE, related_name="versions")
    language = models.CharField(max_length=5, choices=Language.choices)
    headline = models.CharField(max_length=300)
    summary = models.TextField()
    key_facts = models.JSONField(default=list, blank=True)
    explainer = models.JSONField(default=dict, blank=True)  # {reader_situation: text}
    background = models.TextField(blank=True)  # from context library, kept separate from news
    source_version = models.PositiveIntegerField(default=1)
    review_status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_versions"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    is_machine_translated = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["snippet", "language"], name="uniq_snippet_language")]

    def __str__(self):
        return f"[{self.language}] {self.headline}"



# Doesn't need to stay because of  jeff
class Interaction(TimeStampedModel):
    """Reader engagement events; like/bookmark are toggles (unique), the rest are event logs."""

    class Kind(models.TextChoices):
        LIKE = "like", "Like"
        SHARE = "share", "Share"
        BOOKMARK = "bookmark", "Bookmark"
        EXPAND = "expand", "Expand"
        READ_THROUGH = "read_through", "Read through"
        VIEW = "view", "View"

    TOGGLE_KINDS = (Kind.LIKE, Kind.BOOKMARK)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interactions")
    snippet = models.ForeignKey(Snippet, on_delete=models.CASCADE, related_name="interactions")
    kind = models.CharField(max_length=20, choices=Kind.choices)

    class Meta:
        indexes = [models.Index(fields=["snippet", "kind", "created_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "snippet", "kind"],
                condition=Q(kind__in=["like", "bookmark"]),
                name="uniq_toggle_interaction",
            )
        ]


class Comment(TimeStampedModel):
    """Threaded reader comment on a snippet."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="snippet_comments")
    snippet = models.ForeignKey(Snippet, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    body = models.TextField(max_length=4000)

    class Meta:
        ordering = ["created_at"]


class SnippetReport(TimeStampedModel):
    """FR-3.10: reader flags a snippet as wrong/outdated → editorial reopen."""

    class Reason(models.TextChoices):
        WRONG = "wrong", "Wrong"
        OUTDATED = "outdated", "Outdated"
        TRANSLATION = "translation", "Bad translation"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    snippet = models.ForeignKey(Snippet, on_delete=models.CASCADE, related_name="reports")
    reason = models.CharField(max_length=20, choices=Reason.choices)
    body = models.TextField(blank=True)
    resolved = models.BooleanField(default=False)
