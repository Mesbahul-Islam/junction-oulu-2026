"""Gameweek and daily scoring. Safe to re-run at any time: scores are recomputed
from PlayerGameStat rows and upserted, so live gameweeks update as games finish."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Sum

from .. import rules
from ..models import DailyScore, Fixture, Gameweek, GameweekScore, PlayerGameStat, Squad, Transfer
from .squads import lineup_for

LOCAL_TZ = ZoneInfo(settings.TIME_ZONE)


def _gameweek_context(gameweek: Gameweek):
    fixtures = list(gameweek.fixtures.all())
    # Per team: are all its fixtures this gameweek finished? (A team with no
    # fixtures counts as done, so its players get auto-subbed.)
    team_done: dict[int, bool] = defaultdict(lambda: True)
    for f in fixtures:
        done = f.status == Fixture.Status.FINISHED
        team_done[f.home_id] = team_done[f.home_id] and done
        team_done[f.away_id] = team_done[f.away_id] and done
    # Per player: points by local date, and whether they played at all.
    by_date: dict[int, dict] = defaultdict(lambda: defaultdict(lambda: Decimal(0)))
    played: set[int] = set()
    for stat in PlayerGameStat.objects.filter(fixture__in=fixtures).select_related("fixture"):
        day = stat.fixture.starts_at.astimezone(LOCAL_TZ).date()
        by_date[stat.player_id][day] += stat.points
        if stat.stats.get("played"):
            played.add(stat.player_id)
    return team_done, by_date, played


def effective_lineup(lineup, team_done, played) -> list[tuple[object, int, bool]]:
    """[(player, multiplier, auto_sub)] for the players who count this gameweek.

    A starter who didn't play is replaced once their team has no games left this
    gameweek, by the first bench player of the same position who did play. The
    captain scores double; if the captain can no longer play, the vice-captain does.
    """
    slots = list(lineup.slots.all())
    starters = [s.player for s in slots if s.is_starter]
    bench = [s.player for s in slots if not s.is_starter]

    def out_for_week(p):
        return p.pk not in played and team_done[p.team_id]

    counting, used_bench = [], set()
    for p in starters:
        if not out_for_week(p):
            counting.append((p, False))
            continue
        sub = next((b for b in bench if b.pk not in used_bench and b.position == p.position and b.pk in played), None)
        if sub is not None:
            used_bench.add(sub.pk)
            counting.append((sub, True))

    captain_id = lineup.captain_id
    if out_for_week(lineup.captain) and not out_for_week(lineup.vice_captain):
        captain_id = lineup.vice_captain_id
    return [(p, rules.CAPTAIN_MULTIPLIER if p.pk == captain_id else 1, auto) for p, auto in counting]


def score_squad(squad: Squad, gameweek: Gameweek, context=None) -> GameweekScore | None:
    lineup = lineup_for(squad, gameweek)
    if lineup is None:
        return None
    team_done, by_date, played = context or _gameweek_context(gameweek)
    counting = effective_lineup(lineup, team_done, played)

    daily: dict = defaultdict(lambda: Decimal(0))
    detail, points = [], Decimal(0)
    for player, multiplier, auto_sub in counting:
        player_points = sum(by_date[player.pk].values(), Decimal(0))
        points += player_points * multiplier
        for day, p in by_date[player.pk].items():
            daily[day] += p * multiplier
        detail.append({"player": player.pk, "points": float(player_points), "multiplier": multiplier, "auto_sub": auto_sub})

    cost = Transfer.objects.filter(squad=squad, gameweek=gameweek).aggregate(s=Sum("point_cost"))["s"] or 0
    final = gameweek.status == Gameweek.Status.FINISHED
    with transaction.atomic():
        existing = GameweekScore.objects.filter(squad=squad, gameweek=gameweek).first()
        newly_final = final and not (existing and existing.final)
        score, _ = GameweekScore.objects.update_or_create(
            squad=squad,
            gameweek=gameweek,
            defaults={"points": points, "transfer_cost": cost, "total": points - cost, "detail": detail, "final": final},
        )
        DailyScore.objects.filter(squad=squad, gameweek=gameweek).exclude(date__in=daily.keys()).delete()
        for day, p in daily.items():
            DailyScore.objects.update_or_create(squad=squad, date=day, defaults={"gameweek": gameweek, "points": p})
        squad.total_points = squad.gameweek_scores.aggregate(s=Sum("total"))["s"] or 0
        fields = ["total_points", "updated_at"]
        if newly_final and gameweek.number >= squad.first_gameweek.number:
            # A new free transfer for the next gameweek, banking up to the max.
            squad.free_transfers = min(squad.free_transfers + 1, rules.MAX_FREE_TRANSFERS)
            fields.append("free_transfers")
        squad.save(update_fields=fields)
    return score


def score_gameweek(gameweek: Gameweek) -> int:
    context = _gameweek_context(gameweek)
    squads = Squad.objects.filter(season=gameweek.season, first_gameweek__number__lte=gameweek.number).select_related(
        "first_gameweek"
    )
    n = 0
    for squad in squads:
        if score_squad(squad, gameweek, context) is not None:
            n += 1
    if gameweek.status == Gameweek.Status.FINISHED:
        from .rewards import award_gameweek  # sponsor vouchers for the gameweek's winners

        award_gameweek(gameweek)
    return n
