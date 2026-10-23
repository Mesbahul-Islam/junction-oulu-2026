"""Celery tasks for markets (virtual points only)."""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import EventMarket, SportEvent
from .services.ledger import MarketError
from .services.settlement import SETTLED, settle_event

logger = logging.getLogger(__name__)

# Events this long past puck-drop without a final score are candidates for score ingestion.
SCORE_INGESTION_GRACE = timedelta(hours=3)


def request_score_ingestion(event: SportEvent) -> None:
    """TODO(score-agent): hook for an agent that fetches the final score + player stats
    (e.g. Liiga public results) and calls services.settlement.ingest_final_score(event, payload).
    Until then admins post scores via POST /api/markets/events/{id}/final-score/."""
    logger.info("Score ingestion needed for event %s (%s)", event.pk, event)


@shared_task(name="apps.markets.tasks.settle_finished_events")
def settle_finished_events() -> dict:
    now = timezone.now()
    # 1. Stop trading on events that have started.
    locked = EventMarket.objects.filter(status=EventMarket.Status.OPEN, event__starts_at__lte=now).update(
        status=EventMarket.Status.LOCKED
    )

    # 2. Settle finished / cancelled events with unsettled markets.
    settled = {}
    events = SportEvent.objects.filter(
        status__in=[SportEvent.Status.FINISHED, SportEvent.Status.CANCELLED]
    ).exclude(markets__isnull=True).distinct()
    for event in events:
        if not event.markets.exclude(status__in=SETTLED).exists():
            continue
        try:
            settled[event.pk] = settle_event(event)
        except MarketError:
            logger.exception("Settlement failed for event %s", event.pk)

    # 3. Ask for scores of events that should be over but have none.
    stale = SportEvent.objects.filter(
        status__in=[SportEvent.Status.SCHEDULED, SportEvent.Status.LIVE],
        starts_at__lte=now - SCORE_INGESTION_GRACE,
    )
    for event in stale:
        request_score_ingestion(event)

    return {"locked_markets": locked, "settled": settled, "awaiting_score": stale.count()}
