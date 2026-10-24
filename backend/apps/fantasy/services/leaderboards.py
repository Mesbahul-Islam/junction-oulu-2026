"""Leaderboards: day / gameweek / season, scoped Finland-wide, to a community or to a league."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from django.db.models import QuerySet

from ..models import DailyScore, Gameweek, GameweekScore, League, Season, Squad
from .squads import FantasyError

PERIODS = ("day", "week", "season")
SCOPES = ("global", "community", "league")


@dataclass
class Row:
    rank: int
    squad_id: int
    squad_name: str
    manager: str
    points: float


def _scoped_squads(season: Season, scope: str, community: str | None, league: League | None) -> QuerySet:
    squads = Squad.objects.filter(season=season)
    if scope == "community":
        if not community:
            raise FantasyError("community scope needs ?community=<slug>")
        squads = squads.filter(user__memberships__community__slug=community).distinct()
    elif scope == "league":
        if league is None:
            raise FantasyError("league scope needs ?league=<id>")
        squads = squads.filter(leagues=league)
    elif scope != "global":
        raise FantasyError(f"scope must be one of {', '.join(SCOPES)}")
    return squads


def leaderboard(season: Season, period: str = "season", scope: str = "global", *, day=None,
                gameweek: Gameweek | None = None, community: str | None = None, league: League | None = None,
                limit: int = 100, user=None) -> dict:
    """Ranked rows (ties share a rank), plus the requesting user's own row."""
    squads = _scoped_squads(season, scope, community, league)
    if period == "season":
        rows = squads.order_by("-total_points", "created_at").values_list(
            "pk", "name", "user__username", "user__email", "total_points"
        )
    elif period == "week":
        if gameweek is None:
            raise FantasyError("week period needs ?gameweek=<number>")
        rows = GameweekScore.objects.filter(gameweek=gameweek, squad__in=squads).order_by("-total", "squad__created_at").values_list(
            "squad_id", "squad__name", "squad__user__username", "squad__user__email", "total"
        )
    elif period == "day":
        if day is None:
            raise FantasyError("day period needs ?date=YYYY-MM-DD")
        rows = DailyScore.objects.filter(date=day, squad__in=squads).order_by("-points", "squad__created_at").values_list(
            "squad_id", "squad__name", "squad__user__username", "squad__user__email", "points"
        )
    else:
        raise FantasyError(f"period must be one of {', '.join(PERIODS)}")

    ranked, me, prev_points, rank = [], None, None, 0
    my_squad_id = None
    if user is not None and user.is_authenticated:
        my_squad_id = squads.filter(user=user).values_list("pk", flat=True).first()
    for i, (squad_id, name, username, email, points) in enumerate(rows, start=1):
        if points != prev_points:
            rank, prev_points = i, points
        row = Row(rank, squad_id, name, username, float(points))
        if i <= limit:
            ranked.append(row)
        if squad_id == my_squad_id:
            me = row
        if i > limit and (me is not None or my_squad_id is None):
            break
    return {"period": period, "scope": scope, "rows": [r.__dict__ for r in ranked], "me": me.__dict__ if me else None}


# --------------------------------------------------------------------------- private leagues

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def create_league(squad: Squad, name: str) -> League:
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
        if not League.objects.filter(code=code).exists():
            break
    league = League.objects.create(season=squad.season, name=name.strip() or "My league", code=code, owner=squad.user)
    league.members.add(squad)
    return league


def join_league(squad: Squad, code: str) -> League:
    league = League.objects.filter(code=(code or "").strip().upper(), season=squad.season).first()
    if league is None:
        raise FantasyError("No league with that code this season")
    league.members.add(squad)
    return league
