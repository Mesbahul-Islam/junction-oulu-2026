"""Game rules and the points formula. Tune freely; everything else reads from here.

Squad shape mirrors Fantasy Premier League (15 players, 11 start, 4 on the
bench) mapped to hockey: two goalies, five defenders and eight forwards; the
starting 11 are one goalie, two defence pairs and two forward lines.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from .models import Position

SQUAD_COMPOSITION = {Position.GOALIE: 2, Position.DEFENCE: 5, Position.FORWARD: 8}
STARTING_COMPOSITION = {Position.GOALIE: 1, Position.DEFENCE: 4, Position.FORWARD: 6}
SQUAD_SIZE = sum(SQUAD_COMPOSITION.values())  # 15
STARTERS = sum(STARTING_COMPOSITION.values())  # 11
MAX_PER_TEAM = 3

CAPTAIN_MULTIPLIER = 2
TRANSFER_POINT_COST = 4  # (legacy) flat cost; transfers now cost by the incoming player's rank, see transfer_cost
MIN_TRANSFER_COST, MAX_TRANSFER_COST = 1, 8


def transfer_cost(percentile: float) -> int:
    """Points you lose to bring a player in, by his season rank within his position.

    percentile 1.0 is the best player at his position (costs MAX_TRANSFER_COST), 0.0 the lowest
    (MIN_TRANSFER_COST). Strong players cost more, so a change has to be worth it."""
    return max(MIN_TRANSFER_COST, min(MAX_TRANSFER_COST, round(MAX_TRANSFER_COST * percentile)))
MAX_FREE_TRANSFERS = 5  # unused free transfers bank up to this many

# --------------------------------------------------------------------------- points

FULL_SHIFT_SECONDS = 15 * 60  # skaters: bonus point for 15+ minutes of ice time
GOAL_POINTS = {Position.GOALIE: 8, Position.DEFENCE: 6, Position.FORWARD: 4}
ASSIST_POINTS = 3
WINNING_GOAL_POINTS = 1
SHOTS_PER_POINT = 3
BLOCKS_PER_POINT = 3
PENALTY_MINUTES_PER_MINUS = 2
MAX_PENALTY_DEDUCTION = 4
DEFENCE_SHUTOUT_POINTS = 3
GOALIE_SAVES_PER_POINT = 5
GOALIE_GOALS_AGAINST_PER_MINUS = 2
GOALIE_WIN_POINTS = 3
GOALIE_SHUTOUT_POINTS = 5


def game_points(position: str, stats: dict) -> tuple[int, dict]:
    """Fantasy points for one player in one game, plus a per-rule breakdown.

    `stats` is the aggregated box score from services.liiga.aggregate_player_stats:
    played, toi, goals, assists, winning_goal, plusminus, shots, blocked_shots,
    penalty_minutes, and for goalies saves, goals_allowed, periods_played; plus
    team context team_won and team_goals_against.
    """
    if not stats.get("played"):
        return 0, {}
    b: dict[str, int] = {"appearance": 1}
    goals, assists = int(stats.get("goals") or 0), int(stats.get("assists") or 0)
    if goals:
        b["goals"] = goals * GOAL_POINTS[position]
    if assists:
        b["assists"] = assists * ASSIST_POINTS
    if stats.get("winning_goal"):
        b["winning_goal"] = WINNING_GOAL_POINTS
    pim = int(stats.get("penalty_minutes") or 0)
    if pim:
        b["penalties"] = -min(pim // PENALTY_MINUTES_PER_MINUS, MAX_PENALTY_DEDUCTION)

    if position == Position.GOALIE:
        saves, against = int(stats.get("saves") or 0), int(stats.get("goals_allowed") or 0)
        if saves // GOALIE_SAVES_PER_POINT:
            b["saves"] = saves // GOALIE_SAVES_PER_POINT
        if against // GOALIE_GOALS_AGAINST_PER_MINUS:
            b["goals_against"] = -(against // GOALIE_GOALS_AGAINST_PER_MINUS)
        if stats.get("goalie_win"):
            b["win"] = GOALIE_WIN_POINTS
        if against == 0 and int(stats.get("periods_played") or 0) >= 3:
            b["shutout"] = GOALIE_SHUTOUT_POINTS
    else:
        if int(stats.get("toi") or 0) >= FULL_SHIFT_SECONDS:
            b["full_shift"] = 1
        pm = int(stats.get("plusminus") or 0)
        if pm:
            b["plus_minus"] = pm
        if int(stats.get("shots") or 0) // SHOTS_PER_POINT:
            b["shots"] = int(stats["shots"]) // SHOTS_PER_POINT
        if int(stats.get("blocked_shots") or 0) // BLOCKS_PER_POINT:
            b["blocks"] = int(stats["blocked_shots"]) // BLOCKS_PER_POINT
        if position == Position.DEFENCE and stats.get("team_goals_against") == 0:
            b["shutout"] = DEFENCE_SHUTOUT_POINTS
    b = {k: v for k, v in b.items() if v}
    return sum(b.values()), b


# --------------------------------------------------------------------------- prices

MIN_PRICE, MAX_PRICE = Decimal("4.0"), Decimal("13.0")
UNPROVEN_PRICE = Decimal("4.5")  # fewer than PRICE_MIN_GAMES games this season
PRICE_MIN_GAMES = 3


def price_for_percentile(pct: float) -> Decimal:
    """Price from a player's points-per-game rank within their position (0 = worst, 1 = best).

    Squared so most players are cheap and only the elite cost 11+: the median
    player costs about 6.0 and a 15-player squad averages ~6.7 under a 100 budget.
    """
    raw = MIN_PRICE + (MAX_PRICE - MIN_PRICE) * Decimal(str(round(pct, 4))) ** 2
    halves = (raw * 2).quantize(Decimal("1"), rounding=ROUND_HALF_UP) / 2
    return min(max(halves, MIN_PRICE), MAX_PRICE).quantize(Decimal("0.1"))
