"""Import a Liiga season and (re)score fantasy gameweeks.

    manage.py sync_liiga                 # current season (2027 = 2026-27): schedule, rosters, all box scores, prices
    manage.py sync_liiga --season 2026   # another season
    manage.py sync_liiga --skip-stats    # schedule and rosters only (fast)
"""

from django.core.management.base import BaseCommand

from apps.fantasy.models import Gameweek, Player
from apps.fantasy.services import liiga, photos
from apps.fantasy.services.scoring import score_gameweek

DEFAULT_SEASON = 2027


class Command(BaseCommand):
    help = "Sync teams, fixtures, players and box scores from the Liiga stats API"

    def add_arguments(self, parser):
        parser.add_argument("--season", type=int, default=DEFAULT_SEASON)
        parser.add_argument("--skip-stats", action="store_true")
        parser.add_argument("--limit", type=int, default=None, help="Max fixtures to backfill stats for")
        parser.add_argument("--no-reprice", action="store_true", help="Keep existing player prices")
        parser.add_argument("--skip-photos", action="store_true", help="Don't make player photo thumbnails")

    def handle(self, *args, season, skip_stats, limit, no_reprice, skip_photos, **opts):
        client = liiga.LiigaClient()
        s = liiga.sync_schedule(client, season)
        self.stdout.write(f"Season {s}: {s.gameweeks.count()} gameweeks, {s.fixtures.count()} fixtures")
        self.stdout.write(f"Players: {liiga.sync_players(client, s)} on rosters")
        if not skip_photos:
            # Small photos made up front, so the app never waits on Liiga's 450 KB originals.
            active = Player.objects.filter(active=True, team__isnull=False)
            self.stdout.write(f"Player photos ready: {photos.generate_thumbnails(active)}")
        if not skip_stats:
            n = liiga.sync_finished_stats(client, s, limit=limit)
            self.stdout.write(f"Box scores synced: {n} fixtures")
            liiga.refresh_gameweeks(s)
        if not no_reprice:
            # Prices are only set for players nobody owns yet, so squads keep their value.
            self.stdout.write(f"Prices updated: {liiga.reprice_players(s, only_new=True)}")
        for gw in Gameweek.objects.filter(season=s).exclude(status=Gameweek.Status.UPCOMING):
            score_gameweek(gw)
        self.stdout.write(self.style.SUCCESS("Done"))
