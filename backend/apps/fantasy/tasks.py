"""Keeps fantasy data in step with Liiga: schedule daily, live box scores every 10 minutes."""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Fixture, Gameweek, Season
from .services import liiga
from .services.scoring import score_gameweek

logger = logging.getLogger(__name__)

# How long after puck drop we keep polling a game for its box score.
LIVE_WINDOW = timedelta(hours=6)


@shared_task(name="apps.fantasy.tasks.sync_schedule")
def sync_schedule() -> dict:
    season = Season.objects.filter(is_current=True).first()
    if season is None:
        return {"skipped": "no current season; run manage.py sync_liiga"}
    client = liiga.LiigaClient()
    liiga.sync_schedule(client, season.liiga_season)
    return {"players": liiga.sync_players(client, season)}


@shared_task(name="apps.fantasy.tasks.sync_live")
def sync_live() -> dict:
    season = Season.objects.filter(is_current=True).first()
    if season is None:
        return {"skipped": "no current season"}
    now = timezone.now()
    fixtures = season.fixtures.filter(starts_at__lte=now, starts_at__gte=now - LIVE_WINDOW, stats_synced_at__isnull=True)
    client = liiga.LiigaClient()
    gameweeks: set[int] = set()
    for fixture in fixtures.select_related("season", "home", "away"):
        try:
            liiga.sync_fixture_stats(client, fixture)
            if fixture.gameweek_id:
                gameweeks.add(fixture.gameweek_id)
        except Exception:
            logger.exception("Live sync failed for fixture %s", fixture.liiga_id)
    liiga.refresh_gameweeks(season)
    scored = {gw.number: score_gameweek(gw) for gw in Gameweek.objects.filter(pk__in=gameweeks)}
    return {"fixtures": len(fixtures), "scored": scored}
