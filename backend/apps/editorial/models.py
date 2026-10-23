"""Editorial: human-in-the-loop review, verification, standards, audit and corrections
(FR-3.4–3.7, FR-3.13)."""

from django.conf import settings
from django.db import models

from apps.common.choices import Language
from apps.common.models import TimeStampedModel

# FR-3.6: standards checklist applied to every snippet before publication.
# TODO: confirm items and wording against the Council for Mass Media in Finland (JSN)
# Journalist's Guidelines (Journalistin ohjeet) before production use.
STANDARDS_CHECKLIST = [
    "sources_named",
    "ai_role_disclosed",
    "correction_path",
    "editorial_separated_from_ads",
    "privacy_of_named_persons",
]


class ReviewTask(TimeStampedModel):
    """One required human approval (role × optional language) for a snippet (FR-3.4, FR-3.7)."""

    class Reason(models.TextChoices):
        NEW = "new", "New"
        FLAGGED_VERIFICATION = "flagged_verification", "Failed verification"
        FAILED_STANDARDS = "failed_standards", "Failed standards check"
        REPORT = "report", "Reader report"
        LOW_CONFIDENCE = "low_confidence", "Low confidence"
        BATCH_LOW_RISK = "batch_low_risk", "Batch (low risk)"
        REFRESH = "refresh", "Past review-by date"  # FR-3.11

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CHANGES_REQUESTED = "changes_requested", "Changes requested"

    snippet = models.ForeignKey("feed.Snippet", on_delete=models.CASCADE, related_name="review_tasks")
    language = models.CharField(max_length=5, choices=Language.choices, null=True, blank=True)  # null = whole snippet
    required_role = models.CharField(max_length=30)  # accounts.UserRole.Role value
    priority = models.IntegerField(default=0, db_index=True)
    reason = models.CharField(max_length=30, choices=Reason.choices, default=Reason.NEW)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    # Not in contract: False once superseded by a reopen / new review round.
    active = models.BooleanField(default=True, db_index=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_reviews"
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="decided_reviews"
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-priority", "created_at"]

    def __str__(self):
        return f"{self.snippet_id}:{self.required_role}:{self.language or '*'} [{self.status}]"


class VerificationResult(TimeStampedModel):
    """FR-3.5: back-translation / fact consistency check per language."""

    snippet = models.ForeignKey("feed.Snippet", on_delete=models.CASCADE, related_name="verification_results")
    language = models.CharField(max_length=5, choices=Language.choices)
    passed = models.BooleanField(default=False)
    confidence = models.FloatField(default=0.0)
    mismatches = models.JSONField(default=list, blank=True)
    back_translation = models.TextField(blank=True)


class StandardsCheck(TimeStampedModel):
    """FR-3.6: result of STANDARDS_CHECKLIST, `results` = {item: "pass"|"fail"|note}."""

    snippet = models.ForeignKey("feed.Snippet", on_delete=models.CASCADE, related_name="standards_checks")
    results = models.JSONField(default=dict)
    passed = models.BooleanField(default=False)


class AuditLogEntry(TimeStampedModel):
    """FR-3.13: append-only trail of every agent and human action on a snippet."""

    snippet = models.ForeignKey(
        "feed.Snippet", null=True, blank=True, on_delete=models.CASCADE, related_name="audit_log"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    agent = models.CharField(max_length=40, null=True, blank=True)
    action = models.CharField(max_length=60)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name_plural = "audit log entries"


class Correction(TimeStampedModel):
    """FR-3.13: public correction log; created when a published snippet is edited."""

    snippet = models.ForeignKey("feed.Snippet", on_delete=models.CASCADE, related_name="corrections")
    language = models.CharField(max_length=5, choices=Language.choices, null=True, blank=True)
    what_changed = models.TextField()
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]
