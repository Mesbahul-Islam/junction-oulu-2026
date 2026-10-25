"""Perk levels (from the member's trust standing), codes and the ad-free plan."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from .models import LEVEL_ORDER, Level, Perk, Plan, Redemption

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I to misread at a till

# Perks follow the member's trust standing (apps.trust): one ladder, one set of names.
FROM_TRUST = {"member": Level.READER, "contributor": Level.CONTRIBUTOR, "paused": Level.CONTRIBUTOR,
              "eligible": Level.LOCAL_GUIDE, "trusted": Level.TRUSTED}


class PerkError(ValueError):
    pass


def rank(level: str) -> int:
    return LEVEL_ORDER.index(level)


def standing(user) -> dict:
    """The member's best community standing, as a perk level: points, level and what's next."""
    from apps.trust.models import MemberTrust
    from apps.trust.services import CONTRIBUTOR_SCORE, next_step

    rows = MemberTrust.objects.filter(user=user).select_related("community")
    best = max(rows, key=lambda t: (rank(FROM_TRUST[t.level]), t.score), default=None)
    if best is None:
        return {"points": 0, "level": Level.READER, "level_label": Level.READER.label, "community": None,
                "next": {"level": Level.CONTRIBUTOR, "points": CONTRIBUTOR_SCORE}}
    level = FROM_TRUST[best.level]
    nxt = next_step(best)  # {} at eligible and above
    if best.level == "eligible":
        nxt = {"level": Level.TRUSTED, "editor": True}  # an editor approves trusted voices
    elif nxt:
        nxt["level"] = FROM_TRUST[nxt["level"]]
    return {"points": best.score, "level": level, "level_label": Level(level).label,
            "community": best.community.name, "next": nxt or None}


def month_now() -> str:
    return timezone.localdate().strftime("%Y-%m")


def unlocked(perk: Perk, level: str) -> bool:
    return perk.percent_for(level) > 0


def _new_code() -> str:
    return "KALEVA-" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))


def redeem(user, perk: Perk) -> Redemption:
    """Give the member a code for this partner. Asking again in the same month returns the same code."""
    level = standing(user)["level"]
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
