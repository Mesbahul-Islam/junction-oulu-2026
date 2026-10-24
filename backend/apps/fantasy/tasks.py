"""Keeps fantasy data in step with Liiga: schedule daily, live box scores every 10 minutes."""

import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import Fixture, Gameweek, Player, Season
from .services import liiga, photos
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
    players = liiga.sync_players(client, season)
    # Thumbnails for newly added players (existing ones are skipped).
    photos.generate_thumbnails(Player.objects.filter(active=True, team__isnull=False))
    return {"players": players}


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


# --------------------------------------------------------------------------- sports desk agent


@shared_task(name="apps.fantasy.tasks.sports_desk")
def sports_desk() -> dict:
    """Fetch the sports feeds once, then give each followed player his own (rate-limited) task."""
    from .services import sports_desk as desk

    entries = desk.fetch_sports_entries()
    players = list(desk.followed_players())
    about_players = {}
    for player in players:
        matched = [e for e in entries if desk.mentions(e, player)]
        about_players.update({e["url"]: e for e in matched})
        desk_player.delay(player.pk, matched)
    # Stories about followed players go to our newsroom, so readers open them in our app.
    handed = desk.hand_to_newsroom(list(about_players.values()))
    return {"stories": len(entries), "players": len(players), "to_newsroom": handed}


@shared_task(name="apps.fantasy.tasks.desk_player", rate_limit="20/m")
def desk_player(player_id: int, entries: list[dict]) -> dict:
    from .services import sports_desk as desk

    player = Player.objects.select_related("team").filter(pk=player_id).first()
    return desk.run_player(player, entries) if player else {}


@shared_task(name="apps.fantasy.tasks.polish_match", rate_limit="10/m")
def polish_match(fixture_id: int, detail: str, reader: str = "fan", lang: str = "en") -> str:
    """Store an AI-worded match analysis (numbers checked) for readers to get instantly."""
    from .models import Fixture, Report
    from .services import analysis, reports

    fixture = Fixture.objects.select_related("home", "away", "season").get(pk=fixture_id)
    data = analysis.match_analysis(fixture, None, detail, ai=True, reader=reader, lang=lang)
    Report.objects.update_or_create(key=reports.match_key(fixture, detail, reader, lang), defaults={"data": data, "wording": data["source"]})
    return data["source"]


@shared_task(name="apps.fantasy.tasks.polish_coach", rate_limit="10/m")
def polish_coach(squad_id: int, lang: str = "en") -> str:
    from .models import Report, Squad
    from .services import analysis, reports

    squad = Squad.objects.select_related("season", "first_gameweek").get(pk=squad_id)
    key = reports.coach_key(squad, analysis.coach(squad, ai=False, lang=lang))
    data = analysis.coach(squad, ai=True, lang=lang)
    Report.objects.update_or_create(key=key, defaults={"data": data, "wording": data["source"]})
    return data["source"]
