"""Contributor rewards: partner perks unlocked by verified community work.

Readers can also take the ad-free plan (Plan), whatever their level.

A member's level comes from their trust standing (apps.trust, see services.standing): Contributor,
Local guide (trust's "eligible") or Trusted voice. The level unlocks partner perks: discounts and free
items, never cash.
"""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class Level(models.TextChoices):
    READER = "reader", "Reader"
    CONTRIBUTOR = "contributor", "Contributor"
    LOCAL_GUIDE = "local_guide", "Local guide"
    TRUSTED = "trusted", "Trusted voice"


LEVEL_ORDER = [Level.READER, Level.CONTRIBUTOR, Level.LOCAL_GUIDE, Level.TRUSTED]


class Partner(TimeStampedModel):
    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    category = models.CharField(max_length=40)  # "Café", "Sports", "Language school" ...
    city = models.CharField(max_length=60, default="Oulu")
    website = models.URLField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Perk(TimeStampedModel):
    """A partner's offer to contributors. The discount grows with the member's level; 0 means not
    offered at that level, 100 means free."""

    partner = models.OneToOneField(Partner, on_delete=models.CASCADE, related_name="perk")
    title = models.CharField(max_length=120)  # what the discount is on: "coffee and pastries"
    terms = models.CharField(max_length=240, blank=True)
    off_contributor = models.PositiveSmallIntegerField(default=0)
    off_local_guide = models.PositiveSmallIntegerField(default=0)
    off_trusted = models.PositiveSmallIntegerField(default=0)
    code_valid_days = models.PositiveSmallIntegerField(default=14)
    stock = models.PositiveIntegerField(null=True, blank=True)  # codes left this month; empty = no limit
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["partner__name"]

    def __str__(self):
        return f"{self.partner}: {self.title}"

    def percent_for(self, level: str) -> int:
        return {Level.CONTRIBUTOR: self.off_contributor, Level.LOCAL_GUIDE: self.off_local_guide,
                Level.TRUSTED: self.off_trusted}.get(level, 0)

    @property
    def min_level(self) -> str | None:
        return next((lvl for lvl in LEVEL_ORDER[1:] if self.percent_for(lvl)), None)


class Redemption(TimeStampedModel):
    """A code a member took for a partner. One per member, partner and month."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="redemptions")
    perk = models.ForeignKey(Perk, on_delete=models.CASCADE, related_name="redemptions")
    month = models.CharField(max_length=7)  # "2026-10"
    code = models.CharField(max_length=20, unique=True)
    percent = models.PositiveSmallIntegerField(default=0)  # the discount at the member's level when taken
    valid_until = models.DateField()
    used_at = models.DateTimeField(null=True, blank=True)  # marked by the partner

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "perk", "month"], name="one_code_per_perk_per_month")]

    def __str__(self):
        return f"{self.code} ({self.user}, {self.perk})"


class Plan(TimeStampedModel):
    """Ad-free reading, paid by the reader. Open to everyone, contributors included."""

    class Billing(models.TextChoices):
        MONTHLY = "monthly", "€1 a month"
        YEARLY = "yearly", "€10 a year"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="plan")
    billing = models.CharField(max_length=8, choices=Billing.choices)
    renews_on = models.DateField()
    cancelled_at = models.DateTimeField(null=True, blank=True)  # stays ad-free until renews_on

    def __str__(self):
        return f"{self.user}: {self.billing}"
