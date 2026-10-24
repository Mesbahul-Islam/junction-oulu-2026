"""Celery tasks for the AI newsroom.

Beat schedule (``config/celery.py``):

* ``apps.agents.tasks.ingest_all_communities`` - every AGENT_SCHEDULE_MINUTES: one newsroom shift
* ``apps.agents.tasks.expire_snippets`` - every 15 min
"""

from __future__ import annotations

import logging

from celery import shared_task

from . import services
from .models import AgentRun

logger = logging.getLogger(__name__)


# Name kept for the existing django-celery-beat schedule entry.
@shared_task(name="apps.agents.tasks.ingest_all_communities")
def ingest_all_communities() -> int | None:
    """Scheduled shift with the default number of stories, unless one is already going."""
    services.close_stale_runs()
    if services.busy():
        logger.info("Skipping scheduled newsroom run: the previous one is still going")
        return None
    run = services.create_run(AgentRun.Trigger.SCHEDULE)
    run_newsroom.delay(run.pk)
    return run.pk


@shared_task(name="apps.agents.tasks.run_newsroom")
def run_newsroom(run_id: int) -> dict:
    from .newsroom.runner import run_newsroom as run_shift

    run = run_shift(AgentRun.objects.select_related("community").get(pk=run_id))
    return {"run_id": run.pk, "status": run.status, **(run.state.get("result") or {})}


@shared_task(name="apps.agents.tasks.expire_snippets")
def expire_snippets() -> dict:
    return services.expire_snippets()
