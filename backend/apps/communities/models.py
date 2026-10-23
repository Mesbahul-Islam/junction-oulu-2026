"""Communities: groups, membership, posts, contributions, sources, glossary, context library.

FR-1.2 (communities), FR-3.10 (feedback loop), FR-3.12 (community contributions),
FR-3.14 (configurable sources/glossary per community), FR-3.8 (context library).
"""

from django.conf import settings
from django.db import models

from apps.common.choices import Language
from apps.common.models import TimeStampedModel


class CommunityGroup(TimeStampedModel):
    """FR-1.2: geographic (municipality) or topical community."""

    class Kind(models.TextChoices):
        GEO = "geo", "Geographic"
        TOPIC = "topic", "Topic"

    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.GEO)
    municipality = models.CharField(max_length=120, blank=True)
    bbox = models.JSONField(null=True, blank=True)  # [min_lng, min_lat, max_lng, max_lat]
    languages = models.JSONField(default=list, blank=True)  # list of Language codes
    is_active = models.BooleanField(default=True)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="Membership", related_name="communities")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Membership(TimeStampedModel):
    class Role(models.TextChoices):
        MEMBER = "member", "Member"
        COMMUNITY_EDITOR = "community_editor", "Community editor"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships")
    community = models.ForeignKey(CommunityGroup, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        unique_together = [("user", "community")]

    def __str__(self):
        return f"{self.user} @ {self.community} ({self.role})"


class Post(TimeStampedModel):
    """FR-1.2: threaded community post; visible only to members of the community."""

    class Kind(models.TextChoices):
        ANNOUNCEMENT = "announcement", "Announcement"
        POST = "post", "Post"
        DISCUSSION = "discussion", "Discussion"
        SNIPPET = "snippet", "Snippet"

    community = models.ForeignKey(CommunityGroup, on_delete=models.CASCADE, related_name="posts")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.POST)
    body = models.TextField()
    image = models.ImageField(upload_to="posts/", null=True, blank=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind} by {self.author} in {self.community}"


class CommunityContribution(TimeStampedModel):
    """FR-3.10 / FR-3.12: reader input. Never auto-published — always goes through editors."""

    class Kind(models.TextChoices):
        QUESTION = "question", "Question"
        TOPIC_SUGGESTION = "topic_suggestion", "Topic suggestion"
        TIP = "tip", "Tip"
        BRIDGE_STORY = "bridge_story", "Bridge story"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_REVIEW = "in_review", "In review"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        ANSWERED = "answered", "Answered"

    community = models.ForeignKey(CommunityGroup, on_delete=models.CASCADE, related_name="contributions")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="contributions"
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    body = models.TextField()
    normalized_body = models.CharField(max_length=500, blank=True, db_index=True)  # for duplicate detection
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    contributor_consent = models.BooleanField(default=False)
    named_persons_consent = models.BooleanField(default=False)
    occurrence_count = models.PositiveIntegerField(default=1)
    is_story_candidate = models.BooleanField(default=False)  # recurring question -> editorial signal
    linked_snippet = models.ForeignKey(
        "feed.Snippet", null=True, blank=True, on_delete=models.SET_NULL, related_name="contributions"
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.kind}: {self.body[:40]}"


class SourceFeed(TimeStampedModel):
    """FR-3.14: per-community configurable source (no code change needed to add one)."""

    class Kind(models.TextChoices):
        RSS = "rss", "RSS"
        HTML = "html", "HTML"
        API = "api", "API"
        COUNCIL = "council", "Council minutes"

    community = models.ForeignKey(CommunityGroup, on_delete=models.CASCADE, related_name="source_feeds")
    name = models.CharField(max_length=200)
    url = models.URLField(max_length=500)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.RSS)
    is_active = models.BooleanField(default=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("community", "url")]
        ordering = ["name"]

    def __str__(self):
        return self.name


class GlossaryTerm(TimeStampedModel):
    """FR-3.14 / FR-3.9: terminology for explainers & translation (Kela, Migri, verokortti …)."""

    community = models.ForeignKey(
        CommunityGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="glossary_terms"
    )  # null = global
    language = models.CharField(max_length=5, choices=Language.choices)
    term_fi = models.CharField(max_length=200)
    term = models.CharField(max_length=200)
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("community", "language", "term_fi")]
        ordering = ["term_fi"]

    def __str__(self):
        return f"{self.term_fi} → {self.term} ({self.language})"


class ContextEntry(TimeStampedModel):
    """FR-3.8: human-reviewed context library used for snippet background sections."""

    community = models.ForeignKey(
        CommunityGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="context_entries"
    )
    language = models.CharField(max_length=5, choices=Language.choices)
    topic = models.CharField(max_length=200)
    body = models.TextField()
    valid_from = models.DateField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        verbose_name_plural = "context entries"
        ordering = ["topic"]

    def __str__(self):
        return f"{self.topic} ({self.language})"


class FeedbackPrompt(TimeStampedModel):
    """FR-3.10: 'what was useful / what was missing' prompt shown to readers."""

    community = models.ForeignKey(
        CommunityGroup, null=True, blank=True, on_delete=models.CASCADE, related_name="feedback_prompts"
    )
    language = models.CharField(max_length=5, choices=Language.choices, default=Language.ENGLISH)
    question = models.CharField(max_length=300)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.question


class FeedbackResponse(TimeStampedModel):
    prompt = models.ForeignKey(FeedbackPrompt, on_delete=models.CASCADE, related_name="responses")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback_responses"
    )
    snippet = models.ForeignKey(
        "feed.Snippet", null=True, blank=True, on_delete=models.SET_NULL, related_name="feedback_responses"
    )
    useful = models.TextField(blank=True)
    missing = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)  # optional 1–5

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Response to {self.prompt_id}"
