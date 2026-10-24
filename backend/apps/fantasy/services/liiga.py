"""Import from the Liiga stats API (https://prod.liiga-backend.liiga.fi/stats/swagger-ui).

Endpoints used:
  GET /games?season=             schedule + results (with Liiga's gameWeek)
  GET /teams?season=             names, abbreviations, logos
  GET /players/{teamId}?season=  full team roster
  GET /games/{season}/{id}       result, finish type, dressed rosters
  GET /games/{season}/{id}/stats per-period player and goalie stats

Every sync is idempotent: rows are matched on Liiga ids and updated in place.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .. import rules
from ..models import Fixture, Gameweek, Player, PlayerGameStat, Position, Season, Team

logger = logging.getLogger(__name__)

INCLUDED_SERIES = {"RUNKOSARJA", "PLAYOFFS"}  # skip pre-season (PRACTICE) and cups
# Teams whose fans get a local leaderboard: Liiga team slug -> CommunityGroup slug.
TEAM_COMMUNITIES = {"kärpät": "oulu"}


class LiigaClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None, http=None):
        import httpx

        self.base_url = (base_url or settings.LIIGA_API_BASE).rstrip("/")
        headers = {"Accept": "application/json"}
        key = settings.LIIGA_API_KEY if api_key is None else api_key
        if key:
            headers["x-api-key"] = key
        self.http = http or httpx.Client(timeout=30, headers=headers)

    def get(self, path: str, **params):
        resp = self.http.get(f"{self.base_url}{path}", params={k: v for k, v in params.items() if v is not None})
        resp.raise_for_status()
        return resp.json()

    def games(self, season: int) -> list[dict]:
        return self.get("/games", season=season)["games"]

    def teams(self, season: int) -> list[dict]:
        return self.get("/teams", season=season, serie="runkosarja")["teams"]

    def roster(self, team_id: str, season: int) -> list[dict]:
        return self.get(f"/players/{team_id}", season=season)["players"]

    def game(self, season: int, game_id: int) -> dict:
        return self.get(f"/games/{season}/{game_id}")

    def game_stats(self, season: int, game_id: int) -> dict:
        return self.get(f"/games/{season}/{game_id}/stats")


def position_from_role(role: str) -> str:
    role = (role or "").upper()
    if role in ("GOALIE", "GOALKEEPER"):
        return Position.GOALIE
    if "DEFENSEMAN" in role:
        return Position.DEFENCE
    return Position.FORWARD


def _parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _season_name(liiga_season: int) -> str:
    return f"{liiga_season - 1}-{str(liiga_season)[-2:]}"


# --------------------------------------------------------------------------- schedule


def _upsert_team(liiga_id: str, name: str) -> Team:
    team, _ = Team.objects.get_or_create(liiga_id=liiga_id, defaults={"name": name})
    if name and team.name != name:
        team.name = name
        team.save(update_fields=["name", "updated_at"])
    return team


def link_team_communities() -> None:
    from apps.communities.models import CommunityGroup

    for team in Team.objects.filter(community__isnull=True):
        slug = TEAM_COMMUNITIES.get(team.liiga_id.split(":")[-1])
        if slug:
            community = CommunityGroup.objects.filter(slug=slug).first()
            if community:
                team.community = community
                team.save(update_fields=["community", "updated_at"])


def fixture_status(game: dict) -> str:
    if game.get("ended"):
        return Fixture.Status.FINISHED
    if game.get("started"):
        return Fixture.Status.LIVE
    return Fixture.Status.SCHEDULED


def sync_schedule(client: LiigaClient, liiga_season: int, make_current: bool = True) -> Season:
    """Teams, gameweeks and fixtures for a season."""
    season, _ = Season.objects.get_or_create(liiga_season=liiga_season, defaults={"name": _season_name(liiga_season)})
    if make_current and not season.is_current:
        Season.objects.filter(is_current=True).update(is_current=False)
        season.is_current = True
        season.save(update_fields=["is_current", "updated_at"])

    for t in client.teams(liiga_season):
        team = _upsert_team(t["id"], t.get("shortName") or t.get("nameAbbreviation") or t["id"])
        team.abbreviation = t.get("nameAbbreviation") or ""
        team.logo_url = (t.get("logos") or {}).get("lightBg") or ""
        team.save(update_fields=["abbreviation", "logo_url", "updated_at"])

    with transaction.atomic():
        for g in client.games(liiga_season):
            if g.get("serie") not in INCLUDED_SERIES or not g.get("gameWeek"):
                continue
            home = _upsert_team(g["homeTeam"]["teamId"], g["homeTeam"].get("teamName") or "")
            away = _upsert_team(g["awayTeam"]["teamId"], g["awayTeam"].get("teamName") or "")
            gameweek, _ = Gameweek.objects.get_or_create(season=season, number=g["gameWeek"])
            status = fixture_status(g)
            Fixture.objects.update_or_create(
                season=season,
                liiga_id=g["id"],
                defaults={
                    "gameweek": gameweek,
                    "serie": g["serie"],
                    "home": home,
                    "away": away,
                    "starts_at": _parse_dt(g["start"]),
                    "status": status,
                    "home_goals": g["homeTeam"].get("goals") if status != Fixture.Status.SCHEDULED else None,
                    "away_goals": g["awayTeam"].get("goals") if status != Fixture.Status.SCHEDULED else None,
                    "finished_type": g.get("finishedType") or "",
                },
            )
        refresh_gameweeks(season)
    link_team_communities()
    return season


def refresh_gameweeks(season: Season) -> None:
    """Deadline = first puck drop; status from the fixtures' states."""
    now = timezone.now()
    for gw in season.gameweeks.all():
        fixtures = list(gw.fixtures.all())
        if not fixtures:
            continue
        gw.deadline = min(f.starts_at for f in fixtures)
        if all(f.status == Fixture.Status.FINISHED and f.stats_synced_at for f in fixtures):
            gw.status = Gameweek.Status.FINISHED
        elif gw.deadline <= now:
            gw.status = Gameweek.Status.LIVE
        else:
            gw.status = Gameweek.Status.UPCOMING
        gw.save(update_fields=["deadline", "status", "updated_at"])


# --------------------------------------------------------------------------- players


def _upsert_player(p: dict, team: Team | None) -> Player:
    defaults = {
        "first_name": p.get("firstName") or "",
        "last_name": p.get("lastName") or "",
        "position": position_from_role(p.get("role")),
        "liiga_role": p.get("role") or "",
        "jersey": p.get("jersey"),
        "nationality": p.get("nationality") or "",
        "picture_url": p.get("pictureUrl") or "",
        "injured": bool(p.get("injured")),
        "suspended": bool(p.get("suspended")),
        "active": not p.get("removed"),
    }
    if team is not None:
        defaults["team"] = team
    player, _ = Player.objects.update_or_create(liiga_id=p["id"], defaults=defaults)
    return player


def sync_players(client: LiigaClient, season: Season) -> int:
    """Full rosters of every team in the season. Players no longer listed become inactive."""
    seen: set[int] = set()
    teams = Team.objects.filter(Q(home_fixtures__season=season) | Q(away_fixtures__season=season)).distinct()
    for team in teams:
        for p in client.roster(team.liiga_id, season.liiga_season):
            if p.get("removed"):
                continue
            _upsert_player(p, team)
            seen.add(p["id"])
    Player.objects.filter(team__in=teams).exclude(liiga_id__in=seen).update(active=False)
    return len(seen)


def reprice_players(season: Season, only_new: bool = False) -> int:
    """Set prices from this season's points-per-game rank within each position
    (see rules.price_for_percentile). only_new leaves owned players' prices alone."""
    totals = {
        row["player"]: row
        for row in PlayerGameStat.objects.filter(fixture__season=season, stats__played=True)
        .values("player")
        .annotate(points=Sum("points"), games=Count("id"))
    }
    prices: dict[int, Decimal] = {}
    players = list(Player.objects.filter(team__isnull=False))
    for position in Position.values:
        ranked = sorted(
            (p for p in players if p.position == position and totals.get(p.pk, {}).get("games", 0) >= rules.PRICE_MIN_GAMES),
            key=lambda p: totals[p.pk]["points"] / totals[p.pk]["games"],
        )
        for i, p in enumerate(ranked):
            prices[p.pk] = rules.price_for_percentile(i / (len(ranked) - 1) if len(ranked) > 1 else 1.0)
    owned = set(Player.objects.filter(squad_picks__isnull=False).values_list("pk", flat=True)) if only_new else set()
    n = 0
    for player in players:
        price = prices.get(player.pk, rules.UNPROVEN_PRICE)
        if player.pk not in owned and price != player.price:
            player.price = price
            player.save(update_fields=["price", "updated_at"])
            n += 1
    return n


def refresh_player_totals(season: Season, player_ids=None) -> None:
    qs = Player.objects.all() if player_ids is None else Player.objects.filter(pk__in=player_ids)
    totals = dict(
        PlayerGameStat.objects.filter(fixture__season=season, player__in=qs)
        .values_list("player")
        .annotate(s=Sum("points"))
    )
    for player in qs:
        total = totals.get(player.pk) or 0
        if player.total_points != total:
            player.total_points = total
            player.save(update_fields=["total_points", "updated_at"])


# --------------------------------------------------------------------------- box scores


def aggregate_player_stats(stats_payload: dict, side: str) -> dict[int, dict]:
    """Sum one team's per-period skater and goalie rows into a box score per player.

    side: "homeTeam" or "awayTeam".
    """
    out: dict[int, dict] = defaultdict(lambda: defaultdict(int))
    for block in stats_payload.get(side) or []:
        for row in block.get("periodPlayerStats") or []:
            p, s = row.get("period") or {}, out[row["playerId"]]
            s["goals"] += p.get("goals") or 0
            s["assists"] += p.get("assists") or 0
            s["plusminus"] += p.get("plusminus") or 0
            s["shots"] += p.get("shots") or 0
            s["blocked_shots"] += p.get("blockedShots") or 0
            s["penalty_minutes"] += p.get("penaltyminutes") or 0
            s["toi"] += p.get("timeofice") or 0
            s["winning_goal"] = int(bool(s["winning_goal"] or p.get("winningGoal")))
        for row in block.get("goaliePeriodStats") or []:
            p, s = row.get("period") or {}, out[row["playerId"]]
            saves, against = p.get("saves") or 0, p.get("goalsAllowed") or 0
            s["goalie"] = 1
            s["saves"] += saves
            s["goals_allowed"] += against
            s["goals"] += p.get("goals") or 0
            s["assists"] += p.get("assists") or 0
            s["penalty_minutes"] += p.get("penaltyminutes") or 0
            if saves or against or p.get("shotsOnGoal"):
                s["periods_played"] += 1
    result = {}
    for pid, s in out.items():
        s = dict(s)
        s["played"] = bool(s.get("periods_played")) if s.get("goalie") else s.get("toi", 0) > 0
        result[pid] = s
    return result


def sync_fixture_stats(client: LiigaClient, fixture: Fixture) -> int:
    """Result + per-player fantasy points for one fixture. Returns rows written."""
    season = fixture.season.liiga_season
    detail = client.game(season, fixture.liiga_id)
    game = detail.get("game") or {}
    fixture.status = fixture_status(game)
    fixture.home_goals = (game.get("homeTeam") or {}).get("goals")
    fixture.away_goals = (game.get("awayTeam") or {}).get("goals")
    fixture.finished_type = game.get("finishedType") or ""

    # Roster players seen for the first time (call-ups) are created on the fly.
    for side_key, team in (("homeTeamPlayers", fixture.home), ("awayTeamPlayers", fixture.away)):
        for p in detail.get(side_key) or []:
            if not Player.objects.filter(liiga_id=p["id"]).exists():
                _upsert_player(p, team)

    if fixture.status == Fixture.Status.SCHEDULED:
        fixture.save()
        return 0

    payload = client.game_stats(season, fixture.liiga_id)
    home_goals, away_goals = fixture.home_goals or 0, fixture.away_goals or 0
    written, touched = 0, []
    with transaction.atomic():
        for side, goals_for, goals_against in (("homeTeam", home_goals, away_goals), ("awayTeam", away_goals, home_goals)):
            boxes = aggregate_player_stats(payload, side)
            team_won = fixture.status == Fixture.Status.FINISHED and goals_for > goals_against
            goalies_played = sorted(
                (pid for pid, s in boxes.items() if s.get("goalie") and s["played"]),
                key=lambda pid: boxes[pid].get("periods_played", 0),
                reverse=True,
            )
            players = {p.liiga_id: p for p in Player.objects.filter(liiga_id__in=boxes.keys())}
            for liiga_id, box in boxes.items():
                player = players.get(liiga_id)
                if player is None:
                    continue
                box["team_won"] = team_won
                box["team_goals_against"] = goals_against if fixture.status == Fixture.Status.FINISHED else None
                box["goalie_win"] = bool(team_won and goalies_played and goalies_played[0] == liiga_id)
                points, breakdown = rules.game_points(player.position, box)
                PlayerGameStat.objects.update_or_create(
                    player=player, fixture=fixture, defaults={"stats": box, "breakdown": breakdown, "points": points}
                )
                touched.append(player.pk)
                written += 1
        if fixture.status == Fixture.Status.FINISHED:
            fixture.stats_synced_at = timezone.now()
        fixture.save()
    refresh_player_totals(fixture.season, touched)
    return written


def sync_finished_stats(client: LiigaClient, season: Season, limit: int | None = None) -> int:
    """Box scores for finished fixtures that haven't been synced yet (backfill)."""
    qs = season.fixtures.filter(status=Fixture.Status.FINISHED, stats_synced_at__isnull=True).order_by("starts_at")
    n = 0
    for fixture in qs[:limit] if limit else qs:
        try:
            sync_fixture_stats(client, fixture)
            n += 1
        except Exception:  # one bad game shouldn't stop the backfill
            logger.exception("Stats sync failed for fixture %s", fixture.liiga_id)
    return n
