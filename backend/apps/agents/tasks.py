"""Celery tasks for the AI newsroom.

Beat (config/celery.py):
* ``apps.agents.tasks.ingest_all_communities`` - every 30 min
* ``apps.agents.tasks.expire_snippets`` - every 15 min
"""

from __future__ import annotations

import logging

from celery import shared_task
from django.apps import apps

from . import services
from .models import AgentRun

logger = logging.getLogger(__name__)


def _get_or_create_run(community_id: int, run_id: int | None, trigger: str) -> AgentRun:
    if run_id:
        return AgentRun.objects.get(pk=run_id)
    return AgentRun.objects.create(community_id=community_id, trigger=trigger)


@shared_task(name="apps.agents.tasks.ingest_all_communities")
def ingest_all_communities() -> list[int]:
    """Queue one ingest run per active community that has active source feeds
    or open community contributions."""
    CommunityGroup = apps.get_model("communities", "CommunityGroup")
    SourceFeed = apps.get_model("communities", "SourceFeed")
    Contribution = apps.get_model("communities", "CommunityContribution")
    queued = []
    for community_id in CommunityGroup.objects.filter(is_active=True).values_list("pk", flat=True):
        has_feeds = SourceFeed.objects.filter(community_id=community_id, is_active=True).exists()
        has_signals = Contribution.objects.filter(community_id=community_id, status="new").exists()
        if has_feeds or has_signals:
            ingest_and_run.delay(community_id, trigger=AgentRun.Trigger.SCHEDULE)
            queued.append(community_id)
    return queued


@shared_task(name="apps.agents.tasks.ingest_and_run")
def ingest_and_run(community_id: int, run_id: int | None = None, trigger: str = AgentRun.Trigger.SCHEDULE, **options) -> dict:
    """Scout the community's feeds + signals, run the full graph, persist for review."""
    run = _get_or_create_run(community_id, run_id, trigger)
    state = services.initial_state(run, fetch=True, **options)
    snippets = services.execute_run(run, state)
    return {"run_id": run.pk, "snippets": [s.pk for s in snippets]}


@shared_task(name="apps.agents.tasks.run_graph_for_sources")
def run_graph_for_sources(community_id: int, source_ids: list[int], run_id: int | None = None,
                          trigger: str = AgentRun.Trigger.MANUAL, **options) -> dict:
    """Run the graph on already-stored SourceDocuments (no fetching)."""
    run = _get_or_create_run(community_id, run_id, trigger)
    state = services.initial_state(run, source_ids=source_ids, fetch=False, **options)
    snippets = services.execute_run(run, state)
    return {"run_id": run.pk, "snippets": [s.pk for s in snippets]}


@shared_task(name="apps.agents.tasks.expire_snippets")
def expire_snippets() -> dict:
    """Published snippets past ``expires_at`` -> ``expired``; past ``review_by`` ->
    editorial refresh task (TODO: "refresh" reason in editorial)."""
    return services.expire_snippets()
