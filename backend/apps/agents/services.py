"""AI newsroom services: start a shift, send ready stories, expire old ones.

The newsroom itself lives in ``apps/agents/newsroom/`` (see ``runner.py``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Max
from django.utils import timezone

from apps.common.choices import SAMI_LANGUAGES, ReviewStatus

from .models import AgentRun

logger = logging.getLogger(__name__)

AGENT_NAME = "newsroom"


def newsroom_community():
    """The community the newsroom writes for: Oulu, else the first active geographic community.

    The Kaleva feed itself is fixed in ``newsroom/wire.py``; the community only decides the
    audience (languages, readers) the stories are written and ranked for.
    """
    CommunityGroup = apps.get_model("communities", "CommunityGroup")
    active = CommunityGroup.objects.filter(is_active=True)
    return (active.filter(slug="oulu").first()
            or active.filter(kind=CommunityGroup.Kind.GEO).order_by("pk").first())


def busy() -> bool:
    return AgentRun.objects.filter(status__in=[AgentRun.Status.QUEUED, AgentRun.Status.RUNNING]).exists()


def cities():
    """The towns the newsroom can run for: active geographic communities, oldest run first."""
    CommunityGroup = apps.get_model("communities", "CommunityGroup")
    return (CommunityGroup.objects.filter(kind=CommunityGroup.Kind.GEO, is_active=True)
            .annotate(last_run_at=Max("agent_runs__created_at"), member_count=Count("memberships", distinct=True))
            .order_by(F("last_run_at").asc(nulls_first=True), "name"))


def add_city(municipality_code: str):
    """Start covering a municipality: a geographic community with its Statistics Finland figures.
    Its languages start as Oulu's (or the first town's); members' own languages are added per run."""
    from django.utils.text import slugify

    from apps.communities import demographics, places

    CommunityGroup = apps.get_model("communities", "CommunityGroup")
    name = places.municipality_name(municipality_code)
    if not name:
        raise ValidationError("Unknown municipality.")
    if CommunityGroup.objects.filter(kind=CommunityGroup.Kind.GEO, municipality__iexact=name).exists():
        raise ValidationError(f"{name} is already covered.")
    template = newsroom_community()
    slug, n = slugify(name) or municipality_code, 2
    while CommunityGroup.objects.filter(slug=slug).exists():
        slug, n = f"{slugify(name)}-{n}", n + 1
    city = CommunityGroup.objects.create(
        name=name, slug=slug, kind=CommunityGroup.Kind.GEO, municipality=name, municipality_code=municipality_code,
        languages=list(template.languages) if template else ["fi", "en"],
        description=f"Local news and neighbours in {name}",
    )
    try:
        demographics.refresh(city)
    except demographics.DemographicsError:
        pass  # the town still works; Jev just gets no public figures for it
    # Readers who live there (until now served by the nearest covered town) get their own town.
    from apps.communities.services import join_community

    for user in get_user_model().objects.filter(profile__location__municipality__iexact=name):
        join_community(user, city)
    return city


def create_run(trigger: str, max_stories: int | None = None, community=None) -> AgentRun:
    """A shift for ``community`` (a town). Scheduled shifts take turns: the town whose last
    shift is oldest goes next."""
    if community is None:
        community = cities().first() if trigger == AgentRun.Trigger.SCHEDULE else newsroom_community()
    if community is None:
        raise ValidationError("No active community to write for. Run `manage.py seed_demo` first.")
    return AgentRun.objects.create(
        community=community, trigger=trigger, max_stories=max_stories or settings.AGENT_MAX_ITEMS,
    )


def close_stale_runs(hours: int = 2) -> int:
    """Runs still 'queued'/'running' after ``hours`` were lost (e.g. the worker restarted)."""
    return AgentRun.objects.filter(
        status__in=[AgentRun.Status.QUEUED, AgentRun.Status.RUNNING], created_at__lt=timezone.now() - timedelta(hours=hours),
    ).update(status=AgentRun.Status.FAILED, error="Never finished (worker restarted or timed out)",
             finished_at=timezone.now(), desk="")


@transaction.atomic
def send_story(snippet, user) -> bool:
    """One-click publish of a story the newsroom marked "Ready to send". A person still does
    it: their name goes on every approval and in the audit log."""
    from apps.editorial import services as editorial

    ReviewTask = apps.get_model("editorial", "ReviewTask")
    if snippet.review_status == ReviewStatus.PUBLISHED:
        return True
    if snippet.review_level != "ready":
        raise ValidationError("This story needs an editor's review in the Editor queue.")
    now = timezone.now()
    ReviewTask.objects.filter(snippet=snippet, active=True, status=ReviewTask.Status.OPEN).update(
        status=ReviewTask.Status.APPROVED, decided_by=user, decided_at=now,
    )
    snippet.versions.exclude(language__in=SAMI_LANGUAGES).update(
        review_status=ReviewStatus.APPROVED, approved_by=user, approved_at=now,
    )
    editorial.log(snippet, "sent_without_review", actor=user, payload={"verdict": "ready"})
    return editorial.publish(snippet)


def expire_snippets(now: datetime | None = None) -> dict[str, int]:
    """Published stories past ``expires_at`` expire; past ``review_by`` go back to an editor."""
    from apps.editorial import services as editorial

    Snippet = apps.get_model("feed", "Snippet")
    now = now or timezone.now()
    expired = 0
    for snippet in Snippet.objects.filter(review_status=ReviewStatus.PUBLISHED, expires_at__lt=now):
        snippet.review_status = ReviewStatus.EXPIRED
        snippet.save(update_fields=["review_status", "updated_at"])
        editorial.log(snippet, "expired", agent=AGENT_NAME, payload={"expires_at": snippet.expires_at.isoformat()})
        expired += 1
    refreshed = 0
    for snippet in Snippet.objects.filter(review_status=ReviewStatus.PUBLISHED, review_by__lt=now):
        editorial.enqueue(snippet, "refresh")
        snippet.review_by = None  # don't re-enqueue every 15 minutes
        snippet.save(update_fields=["review_by", "updated_at"])
        refreshed += 1
    return {"expired": expired, "refresh_enqueued": refreshed}
