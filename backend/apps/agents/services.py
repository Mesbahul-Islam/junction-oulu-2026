"""AI newsroom services: start a shift, send ready stories, expire old ones.

The newsroom itself lives in ``apps/agents/newsroom/`` (see ``runner.py``).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.choices import SAMI_LANGUAGES, ReviewStatus

from .models import AgentRun

logger = logging.getLogger(__name__)

AGENT_NAME = "newsroom"


def newsroom_community():
    """The community whose Kaleva feeds the newsroom reads (the first one with active feeds)."""
    CommunityGroup = apps.get_model("communities", "CommunityGroup")
    return (CommunityGroup.objects.filter(is_active=True, source_feeds__is_active=True)
            .distinct().order_by("pk").first())


def busy() -> bool:
    return AgentRun.objects.filter(status__in=[AgentRun.Status.QUEUED, AgentRun.Status.RUNNING]).exists()


def create_run(trigger: str, max_stories: int | None = None) -> AgentRun:
    community = newsroom_community()
    if community is None:
        raise ValidationError("No community has an active RSS feed. Run `manage.py seed_demo` first.")
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
