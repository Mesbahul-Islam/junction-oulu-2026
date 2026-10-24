"""Accounts: users, profiles, interests, roles, QR onboarding links (FR-1.1, FR-3.11)."""

import re

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from apps.common.choices import Language, ReaderSituation
from apps.common.models import TimeStampedModel


USERNAME_RE = r"^[A-Za-z0-9_.]{3,30}$"
username_validator = RegexValidator(USERNAME_RE, "3–30 letters, digits, _ or . (no spaces).")


def suggest_username(base: str, exclude_pk=None) -> str:
    """A free username made from ``base`` (e.g. the email's first part): "aino", "aino2", ..."""
    stem = re.sub(r"[^A-Za-z0-9_.]", "", (base or "").split("@")[0])[:26] or "reader"
    stem = stem if len(stem) >= 3 else f"{stem}_reader"[:26]
    taken = User.objects.exclude(pk=exclude_pk)
    name, n = stem, 1
    while taken.filter(username__iexact=name).exists():
        n += 1
        name = f"{stem}{n}"
    return name


class UserManager(BaseUserManager):
    """Manager for an email-as-username user model."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Superuser must have is_staff=True and is_superuser=True")
        return self._create_user(email, password, **extra)


class User(AbstractUser, TimeStampedModel):
    """FR-1.1: account identified by email (password or Google OAuth via allauth)."""

    email = models.EmailField(unique=True)
    # Public handle (@username) shown on posts, comments and leaderboards; sign-in stays by email.
    username = models.CharField(max_length=30, validators=[username_validator])
    display_name = models.CharField(max_length=120, blank=True)
    preferred_language = models.CharField(max_length=5, choices=Language.choices, default=Language.FINNISH)
    reader_situation = models.CharField(
        max_length=20, choices=ReaderSituation.choices, default=ReaderSituation.RESIDENT
    )
    arrival_date = models.DateField(null=True, blank=True)  # FR-3.11 arrival-day buckets
    onboarded = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    objects = UserManager()

    class Meta(AbstractUser.Meta):
        constraints = [models.UniqueConstraint(Lower("username"), name="uniq_username_ci")]

    def save(self, *args, **kwargs):
        if not self.username:  # Google sign-in, admin, demo data: made from the email, changeable later
            self.username = suggest_username(self.email, exclude_pk=self.pk)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Interest(TimeStampedModel):
    """Interest taxonomy used for onboarding and feed personalisation (FR-1.1)."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Location(TimeStampedModel):
    """User-supplied location (postal code or coordinates) mapped to a municipality."""

    name = models.CharField(max_length=120, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    municipality = models.CharField(max_length=120, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name or self.postal_code or self.municipality or f"{self.lat},{self.lng}"


class Profile(TimeStampedModel):
    """FR-1.1: 1:1 with User, auto-created by post_save signal."""

    user = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="profile")
    interests = models.ManyToManyField(Interest, blank=True, related_name="profiles")
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.SET_NULL, related_name="profiles")
    interest_vector = models.JSONField(default=dict, blank=True)  # slug -> weight

    def __str__(self):
        return f"Profile<{self.user_id}>"


class UserRole(TimeStampedModel):
    """Editorial / community roles, optionally scoped to language and community."""

    class Role(models.TextChoices):
        NEWS_EDITOR = "news_editor", "News editor"
        EDITOR = "editor", "Editor"
        STANDARDS_EDITOR = "standards_editor", "Standards editor"
        LANGUAGE_REVIEWER = "language_reviewer", "Language reviewer"
        COMMUNITY_EDITOR = "community_editor", "Community editor"
        ADMIN = "admin", "Admin"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="roles")
    role = models.CharField(max_length=30, choices=Role.choices)
    language = models.CharField(max_length=5, choices=Language.choices, null=True, blank=True)
    community = models.ForeignKey(
        "communities.CommunityGroup", null=True, blank=True, on_delete=models.CASCADE, related_name="user_roles"
    )

    class Meta:
        unique_together = [("user", "role", "language", "community")]

    def __str__(self):
        return f"{self.user} {self.role}"


class OnboardingLink(TimeStampedModel):
    """FR-3.11: QR-code onboarding link (e.g. printed at service points / housing)."""

    code = models.CharField(max_length=40, unique=True)
    community = models.ForeignKey(
        "communities.CommunityGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="onboarding_links"
    )
    language = models.CharField(max_length=5, choices=Language.choices, null=True, blank=True)
    default_arrival_offset_days = models.IntegerField(default=0)

    def __str__(self):
        return self.code
