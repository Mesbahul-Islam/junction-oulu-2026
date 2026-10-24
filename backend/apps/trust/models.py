"""Trusted community voices.

Each member gets a trust score per community, built only from things others verified: notes rated
helpful by people in different situations, questions and tips the editors accepted, likes from other
members, ratings that matched a note's final verdict. A high score makes a member *eligible*;
a person (community editor or admin) decides who becomes a trusted voice.
"""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class MemberTrust(TimeStampedModel):
    class Level(models.TextChoices):
        MEMBER = "member", "Member"
        CONTRIBUTOR = "contributor", "Contributor"
        ELIGIBLE = "eligible", "Eligible: waiting for an editor"
        TRUSTED = "trusted", "Trusted voice"
        PAUSED = "paused", "Paused: no longer meets the bar"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="trust")
    community = models.ForeignKey("communities.CommunityGroup", on_delete=models.CASCADE, related_name="trust")
    score = models.IntegerField(default=0)
    verified = models.PositiveIntegerField(default=0)  # helpful notes + accepted questions and tips
    breakdown = models.JSONField(default=dict, blank=True)  # {signal: {"count": n, "points": p}}
    level = models.CharField(max_length=12, choices=Level.choices, default=Level.MEMBER, db_index=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="trust_approvals"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-score"]
        constraints = [models.UniqueConstraint(fields=["user", "community"], name="uniq_trust_per_community")]

    def __str__(self):
        return f"{self.user} @ {self.community}: {self.score} ({self.level})"
