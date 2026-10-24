"""Points, levels and codes. All numbers are in POINTS and the thresholds below."""

from __future__ import annotations

import secrets
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import LEVEL_ORDER, ContributorStats, Level, Perk, Plan, Redemption

POINTS = {
    "posts_approved": 10,        # a post an editor approved
    "photos_approved": 5,        # a photo that passed the moderator check
    "corrections_accepted": 15,  # a correction or fact check the newsroom accepted
    "rejected": -5,              # rejected or removed: costs points, so quantity alone doesn't pay
}
CONTRIBUTOR_POINTS = 10
GUIDE_POINTS = 60
GUIDE_RATING = Decimal("4.0")  # average rating from other members, out of 5
GUIDE_RATINGS = 5              # ...over at least this many ratings
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to misread at a till


class StatsError(ValueError):
    pass


class PerkError(ValueError):
    pass


def points_for(stats: ContributorStats) -> int:
    return max(0, sum(getattr(stats, field) * value for field, value in POINTS.items()))


def level_for(stats: ContributorStats) -> str:
    """Trusted voice comes from an editor's approval, not from points."""
    if stats.trusted_voice:
        return Level.TRUSTED
    if (stats.points >= GUIDE_POINTS and stats.rating_count >= GUIDE_RATINGS
            and stats.rating_average >= GUIDE_RATING):
        return Level.LOCAL_GUIDE
    return Level.CONTRIBUTOR if stats.points >= CONTRIBUTOR_POINTS else Level.READER


def rank(level: str) -> int:
    return LEVEL_ORDER.index(level)


def next_step(stats: ContributorStats | None) -> dict | None:
    """What is still missing for the next level, or None at the top."""
    points = stats.points if stats else 0
    level = stats.level if stats else Level.READER
    if level == Level.READER:
        return {"level": Level.CONTRIBUTOR, "points": CONTRIBUTOR_POINTS - points}
    if level == Level.CONTRIBUTOR:
        return {"level": Level.LOCAL_GUIDE, "points": max(0, GUIDE_POINTS - points),
                "ratings": max(0, GUIDE_RATINGS - stats.rating_count),
                "rating_average": str(GUIDE_RATING) if stats.rating_average < GUIDE_RATING else None}
    if level == Level.LOCAL_GUIDE:
        return {"level": Level.TRUSTED, "editor": True}  # an editor approves trusted voices
    return None


def _user_for(row: dict):
    User = get_user_model()
    if row.get("user_id"):
        return User.objects.filter(pk=row["user_id"]).first()
    if row.get("email"):
        return User.objects.filter(email__iexact=row["email"]).first()
    if row.get("username"):
        return User.objects.filter(username__iexact=row["username"]).first()
    return None


@transaction.atomic
def ingest(rows: list[dict], source: str = "") -> dict:
    """Store the latest statistics for each member in `rows` (validated by IngestSerializer).

    Returns {"stored": [{"user_id", "points", "level"}], "skipped": [{"row", "reason"}]}.
    """
    stored, skipped = [], []
    for i, row in enumerate(rows):
        user = _user_for(row)
        if user is None:
            skipped.append({"row": i, "reason": "no such member"})
            continue
        c, r = row.get("contributions", {}), row.get("community_rating", {})
        stats, _ = ContributorStats.objects.get_or_create(user=user)
        stats.period = row.get("period", "")
        stats.posts_approved = c.get("posts_approved", 0)
        stats.photos_approved = c.get("photos_approved", 0)
        stats.corrections_accepted = c.get("corrections_accepted", 0)
        stats.rejected = c.get("rejected", 0)
        stats.rating_average = r.get("average", 0)
        stats.rating_count = r.get("count", 0)
        stats.trusted_voice = row.get("trusted_voice", False)
        stats.trust_score = row.get("trust_score", 0)
        stats.source = source[:60]
        stats.payload = row.get("_raw", {})
        stats.points = points_for(stats)
        stats.level = level_for(stats)
        stats.save()
        stored.append({"user_id": user.pk, "points": stats.points, "level": stats.level})
    return {"stored": stored, "skipped": skipped}


def month_now() -> str:
    return timezone.localdate().strftime("%Y-%m")


def unlocked(perk: Perk, level: str) -> bool:
    return perk.percent_for(level) > 0


def _new_code() -> str:
    return "KALEVA-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def redeem(user, perk: Perk) -> Redemption:
    """Give the member a code for this partner. Asking again in the same month returns the same code."""
    stats = ContributorStats.objects.filter(user=user).first()
    level = stats.level if stats else Level.READER
    if not perk.active:
        raise PerkError("This offer has ended.")
    if not unlocked(perk, level):
        raise PerkError(f"Unlocks at {Level(perk.min_level).label}." if perk.min_level else "Not offered right now.")
    month = month_now()
    if existing := Redemption.objects.filter(user=user, perk=perk, month=month).first():
        return existing
    with transaction.atomic():
        if perk.stock is not None:
            taken = Perk.objects.filter(pk=perk.pk, stock__gt=0).update(stock=F("stock") - 1)
            if not taken:
                raise PerkError("No codes left this month.")
        for _ in range(5):  # a clash is very unlikely; try a new code if it happens
            try:
                with transaction.atomic():
                    return Redemption.objects.create(
                        user=user, perk=perk, month=month, code=_new_code(), percent=perk.percent_for(level),
                        valid_until=timezone.localdate() + timedelta(days=perk.code_valid_days))
            except IntegrityError:
                if existing := Redemption.objects.filter(user=user, perk=perk, month=month).first():
                    return existing
        raise PerkError("Could not create a code, try again.")


def plan_of(user) -> Plan | None:
    """The member's ad-free plan while it is still running (also after cancelling, until renews_on)."""
    plan = Plan.objects.filter(user=user).first()
    return plan if plan and plan.renews_on >= timezone.localdate() else None


def subscribe(user, billing: str) -> Plan:
    """Start or switch the ad-free plan. Payment is not part of this step."""
    if billing not in Plan.Billing.values:
        raise PerkError("Choose monthly or yearly.")
    today = timezone.localdate()
    renews = today + (timedelta(days=365) if billing == Plan.Billing.YEARLY else timedelta(days=30))
    plan, _ = Plan.objects.update_or_create(user=user, defaults={"billing": billing, "renews_on": renews, "cancelled_at": None})
    return plan


def cancel(user) -> Plan | None:
    plan = plan_of(user)
    if plan and not plan.cancelled_at:
        plan.cancelled_at = timezone.now()
        plan.save(update_fields=["cancelled_at", "updated_at"])
    return plan
