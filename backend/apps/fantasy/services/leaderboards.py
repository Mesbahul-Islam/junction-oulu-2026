"""Leaderboards: day / gameweek / season, scoped Finland-wide, to a community or to a league."""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from django.db.models import QuerySet

from ..models import DailyScore, Gameweek, GameweekScore, League, Season, Squad
from .squads import FantasyError

PERIODS = ("day", "week", "season")
# Manager tiers by season rank: share of all managers at or above you.
TIERS = (("diamond", 0.01), ("gold", 0.10), ("silver", 0.35), ("bronze", 1.0))


def tier_for(rank: int, total: int) -> str:
    """Diamond: top 1% (always at least the leader), gold: top 10%, silver: top 35%, else bronze."""
    if rank == 1:
        return "diamond"
    share = rank / max(total, 1)
    return next(name for name, cut in TIERS if share <= cut)


def season_standing(squad: Squad) -> dict:
    """Your season rank, the number of managers, your tier, and how far the next tier is."""
    total = Squad.objects.filter(season=squad.season).count()
    rank = Squad.objects.filter(season=squad.season, total_points__gt=squad.total_points).count() + 1
    tier = tier_for(rank, total)
    order = [name for name, _ in TIERS]
    nxt = order[order.index(tier) - 1] if tier != "diamond" else None
    target = None
    if nxt:
        cut = dict(TIERS)[nxt]
        target = max(1, int(cut * total)) if nxt != "diamond" else 1
    return {"rank": rank, "managers": total, "tier": tier, "next_tier": nxt,
            "places_to_next": (rank - target) if target else 0}
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
                limit: int = 100, offset: int = 0, user=None) -> dict:
    """One page of ranked rows (ties share a rank), the total, and the requesting user's own row."""
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
    total = 0
    for i, (squad_id, name, username, email, points) in enumerate(rows, start=1):
        total = i
        if points != prev_points:
            rank, prev_points = i, points
        row = Row(rank, squad_id, name, username, float(points))
        if offset < i <= offset + limit:
            ranked.append(row)
        if squad_id == my_squad_id:
            me = row
    return {"period": period, "scope": scope, "total": total, "offset": offset, "limit": limit,
            "rows": [r.__dict__ for r in ranked], "me": me.__dict__ if me else None}


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


def invite_to_league(league: League, inviter: Squad, username: str) -> Squad:
    """A league member adds a friend by @username (the friend needs a squad this season)."""
    if not league.members.filter(pk=inviter.pk).exists():
        raise FantasyError("Only league members can invite friends")
    handle = (username or "").strip().lstrip("@")
    friend = Squad.objects.filter(season=league.season, user__username__iexact=handle).select_related("user").first()
    if friend is None:
        raise FantasyError(f"@{handle} hasn't made a Fantasy Liiga team yet")
    league.members.add(friend)
    return friend


def search_managers(season: Season, query: str, limit: int = 10) -> list[dict]:
    """Managers whose @username starts with `query`, for finding friends to invite."""
    handle = (query or "").strip().lstrip("@")
    if not handle:
        return []
    squads = Squad.objects.filter(season=season, user__username__istartswith=handle).select_related("user")
    return [{"username": s.user.username, "squad_id": s.pk, "squad_name": s.name, "total_points": float(s.total_points)}
            for s in squads.order_by("user__username")[:limit]]
