"""Building squads, making transfers and picking lineups."""

from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .. import rules
from ..models import Gameweek, Lineup, LineupSlot, Player, Season, Squad, SquadPick, Transfer


class FantasyError(Exception):
    pass


def current_season() -> Season:
    season = Season.objects.filter(is_current=True).first()
    if season is None:
        raise FantasyError("No current season. Run `manage.py sync_liiga` first.")
    return season


def next_open_gameweek(season: Season) -> Gameweek:
    """The gameweek that squad, transfer and lineup changes apply to: the next deadline."""
    gw = season.gameweeks.filter(deadline__gt=timezone.now()).order_by("number").first()
    if gw is None:
        raise FantasyError("No upcoming gameweek: the season is over.")
    return gw


def _load_players(player_ids) -> list[Player]:
    try:
        ids = [int(p) for p in player_ids]
    except (TypeError, ValueError):
        raise FantasyError("player ids must be integers") from None
    if len(set(ids)) != len(ids):
        raise FantasyError("A player can only be picked once")
    players = list(Player.objects.select_related("team").filter(pk__in=ids))
    if len(players) != len(ids):
        raise FantasyError("Unknown player id")
    return players


def validate_squad(players: list[Player], budget: Decimal) -> Decimal:
    """Composition, per-team limit and budget. Returns the squad's cost."""
    if len(players) != rules.SQUAD_SIZE:
        raise FantasyError(f"A squad has exactly {rules.SQUAD_SIZE} players")
    counts = Counter(p.position for p in players)
    for position, need in rules.SQUAD_COMPOSITION.items():
        if counts.get(position, 0) != need:
            raise FantasyError(f"A squad needs {need} players in position {position} (got {counts.get(position, 0)})")
    for team, n in Counter(p.team_id for p in players).items():
        if n > rules.MAX_PER_TEAM:
            raise FantasyError(f"At most {rules.MAX_PER_TEAM} players from one team")
    inactive = [p.name for p in players if not p.active]
    if inactive:
        raise FantasyError(f"No longer on a Liiga roster: {', '.join(inactive)}")
    cost = sum((p.price for p in players), Decimal(0))
    if cost > budget:
        raise FantasyError(f"Squad costs {cost}, over the {budget} budget")
    return cost


def default_lineup_order(players: list[Player]) -> list[Player]:
    """Most expensive players start; returns 11 starters followed by the bench."""
    by_price = sorted(players, key=lambda p: (-p.price, -p.total_points, p.pk))
    starters, bench = [], []
    taken = Counter()
    for p in by_price:
        if taken[p.position] < rules.STARTING_COMPOSITION[p.position]:
            starters.append(p)
            taken[p.position] += 1
        else:
            bench.append(p)
    return starters + bench


def _write_lineup(squad: Squad, gameweek: Gameweek, ordered: list[Player], captain: Player, vice: Player) -> Lineup:
    lineup, _ = Lineup.objects.update_or_create(
        squad=squad, gameweek=gameweek, defaults={"captain": captain, "vice_captain": vice}
    )
    lineup.slots.all().delete()
    LineupSlot.objects.bulk_create(
        LineupSlot(lineup=lineup, player=p, slot=i) for i, p in enumerate(ordered, start=1)
    )
    return lineup


def create_squad(user, name: str, player_ids, season: Season | None = None) -> Squad:
    season = season or current_season()
    if Squad.objects.filter(user=user, season=season).exists():
        raise FantasyError("You already have a squad this season; use transfers to change it")
    gameweek = next_open_gameweek(season)
    players = _load_players(player_ids)
    cost = validate_squad(players, season.budget)
    with transaction.atomic():
        squad = Squad.objects.create(
            user=user, season=season, name=name.strip() or "My team", bank=season.budget - cost, first_gameweek=gameweek
        )
        SquadPick.objects.bulk_create(SquadPick(squad=squad, player=p, purchase_price=p.price) for p in players)
        ordered = default_lineup_order(players)
        _write_lineup(squad, gameweek, ordered, captain=ordered[0], vice=ordered[1])
    return squad


def squad_players(squad: Squad) -> list[Player]:
    return [pick.player for pick in squad.picks.select_related("player__team")]


def lineup_for(squad: Squad, gameweek: Gameweek) -> Lineup | None:
    """This gameweek's lineup, or the most recent earlier one carried forward."""
    return (
        squad.lineups.filter(gameweek__season=gameweek.season, gameweek__number__lte=gameweek.number)
        .select_related("gameweek", "captain", "vice_captain")
        .prefetch_related("slots__player")
        .order_by("-gameweek__number")
        .first()
    )


def _editable_lineup(squad: Squad, gameweek: Gameweek) -> Lineup:
    """Lineup row for `gameweek`, copying the carried-forward one if needed."""
    lineup = lineup_for(squad, gameweek)
    if lineup is not None and lineup.gameweek_id == gameweek.pk:
        return lineup
    if lineup is None:
        ordered = default_lineup_order(squad_players(squad))
        return _write_lineup(squad, gameweek, ordered, ordered[0], ordered[1])
    ordered = [s.player for s in lineup.slots.all()]
    return _write_lineup(squad, gameweek, ordered, lineup.captain, lineup.vice_captain)


def set_lineup(squad: Squad, starter_ids, bench_ids, captain_id, vice_captain_id) -> Lineup:
    gameweek = next_open_gameweek(squad.season)
    starters, bench = _load_players(starter_ids), _load_players(bench_ids)
    by_id = {p.pk: p for p in starters + bench}
    starters = [by_id[int(i)] for i in starter_ids]
    bench = [by_id[int(i)] for i in bench_ids]
    owned = {p.pk for p in squad_players(squad)}
    if set(by_id) != owned or len(starters) + len(bench) != rules.SQUAD_SIZE:
        raise FantasyError("Starters and bench must together be exactly your 15 squad players")
    if len(starters) != rules.STARTERS:
        raise FantasyError(f"Pick exactly {rules.STARTERS} starters")
    counts = Counter(p.position for p in starters)
    for position, need in rules.STARTING_COMPOSITION.items():
        if counts.get(position, 0) != need:
            raise FantasyError(f"Starters need {need} players in position {position}")
    starter_ids_set = {p.pk for p in starters}
    try:
        captain_id, vice_captain_id = int(captain_id), int(vice_captain_id)
    except (TypeError, ValueError):
        raise FantasyError("captain and vice_captain must be player ids") from None
    if captain_id not in starter_ids_set or vice_captain_id not in starter_ids_set:
        raise FantasyError("Captain and vice-captain must be starters")
    if captain_id == vice_captain_id:
        raise FantasyError("Captain and vice-captain must be different players")
    with transaction.atomic():
        return _write_lineup(squad, gameweek, starters + bench, by_id[captain_id], by_id[vice_captain_id])


def transfer_costs() -> dict[int, int]:
    """{player_id: points it costs to bring him in}, from his season rank within his position."""
    from django.core.cache import cache

    costs = cache.get("fx-transfer-costs")
    if costs is None:
        costs = {}
        for position in ("G", "D", "F"):
            ids = list(Player.objects.filter(position=position, active=True, team__isnull=False)
                       .order_by("total_points", "pk").values_list("pk", flat=True))
            for i, pid in enumerate(ids):
                costs[pid] = rules.transfer_cost(i / (len(ids) - 1) if len(ids) > 1 else 1.0)
        cache.set("fx-transfer-costs", costs, 600)
    return costs


def changes_are_free(squad: Squad) -> bool:
    """Choosing your team is free; every change after that costs points."""
    return False


def points_available(squad: Squad) -> Decimal:
    """Points you can spend on changes: your season points minus what you've already spent on
    changes for the coming gameweek (those come off when it's scored)."""
    from django.db.models import Sum

    try:
        gameweek = next_open_gameweek(squad.season)
    except FantasyError:
        return Decimal(0)
    spent = squad.transfers.filter(gameweek=gameweek).aggregate(s=Sum("point_cost"))["s"] or 0
    return max(Decimal(0), Decimal(squad.total_points) - spent)


def make_transfers(squad: Squad, out_ids, in_ids) -> list[Transfer]:
    """Swap players for the next gameweek. Each incoming player costs points by his rank
    (see transfer_costs), and you need enough points (points_available) to make the change."""
    if len(out_ids) != len(in_ids) or not out_ids:
        raise FantasyError("Send the same number of players out and in")
    gameweek = next_open_gameweek(squad.season)
    with transaction.atomic():
        squad = Squad.objects.select_for_update().get(pk=squad.pk)
        current = squad_players(squad)
        owned = {p.pk: p for p in current}
        outgoing = _load_players(out_ids)
        incoming = _load_players(in_ids)
        if any(p.pk not in owned for p in outgoing):
            raise FantasyError("You can only transfer out players in your squad")
        if any(p.pk in owned for p in incoming):
            raise FantasyError("That player is already in your squad")
        if sorted(p.position for p in outgoing) != sorted(p.position for p in incoming):
            raise FantasyError("Transfers must swap players of the same position")

        picks = {pick.player_id: pick for pick in squad.picks.all()}
        sale_value = sum((picks[p.pk].purchase_price for p in outgoing), Decimal(0))
        out_pks = {p.pk for p in outgoing}
        validate_squad([p for p in current if p.pk not in out_pks] + incoming, budget=Decimal("Infinity"))
        purchase = sum((p.price for p in incoming), Decimal(0))
        if purchase > squad.bank + sale_value:
            raise FantasyError(f"Not enough money: incoming players cost {purchase}, you have {squad.bank + sale_value}")

        costs = transfer_costs()
        total_cost = sum(costs.get(p.pk, rules.MAX_TRANSFER_COST) for p in incoming)
        available = points_available(squad)
        if total_cost > available:
            raise FantasyError(f"Not enough points: this change costs {total_cost} and you have {available.normalize():f}")
        transfers = []
        # Pair same-position players so the history reads "A out, B in".
        incoming_left = list(incoming)
        for out in outgoing:
            inn = next(p for p in incoming_left if p.position == out.position)
            incoming_left.remove(inn)
            cost = costs.get(inn.pk, rules.MAX_TRANSFER_COST)
            transfers.append(
                Transfer.objects.create(
                    squad=squad, gameweek=gameweek, player_out=out, player_in=inn,
                    price_out=picks[out.pk].purchase_price, price_in=inn.price, point_cost=cost,
                )
            )
            squad.bank += picks[out.pk].purchase_price - inn.price
            picks[out.pk].delete()
            SquadPick.objects.create(squad=squad, player=inn, purchase_price=inn.price)

            lineup = _editable_lineup(squad, gameweek)
            LineupSlot.objects.filter(lineup=lineup, player=out).update(player=inn)
            if lineup.captain_id == out.pk:
                lineup.captain = inn
            if lineup.vice_captain_id == out.pk:
                lineup.vice_captain = inn
            lineup.save(update_fields=["captain", "vice_captain", "updated_at"])
        squad.save(update_fields=["bank", "updated_at"])
    return transfers


def shake_up(squad: Squad, max_points: int, max_changes: int = 3, rng=None) -> list[dict]:
    """Suggest replacing your weakest-form starters with better-form players of the same position,
    picked at random from the strongest options, spending at most `max_points` (and no more than
    you have) and staying within budget. Nothing is changed: the reader saves the suggestion with
    make_transfers. Returns [{"out": Player, "in": Player, "cost": int}]."""
    import random

    from .analysis import games_in, player_form

    rng = rng or random.Random()
    gameweek = next_open_gameweek(squad.season)
    lineup = lineup_for(squad, gameweek)
    current = squad_players(squad)
    owned = {p.pk for p in current}
    starters = [s.player for s in lineup.slots.all() if s.is_starter] if lineup else current
    counts = games_in(gameweek)
    pool = list(Player.objects.filter(active=True, injured=False, suspended=False, team__isnull=False).exclude(pk__in=owned))
    form = player_form([p.pk for p in starters] + [p.pk for p in pool])
    value = lambda p: form.get(p.pk, {}).get("avg", 0) * counts.get(p.team_id, 0)
    costs = transfer_costs()
    picks = {pick.player_id: pick for pick in squad.picks.all()}
    max_points = min(max_points, int(points_available(squad)))

    per_team = defaultdict(int)
    for p in current:
        per_team[p.team_id] += 1
    budget, points_left = squad.bank, max_points
    outs, ins = [], []
    for out in sorted(starters, key=value):
        if len(outs) >= max_changes:
            break
        money = budget + picks[out.pk].purchase_price
        options = [p for p in pool if p.position == out.position and p.pk not in {i.pk for i in ins}
                   and p.price <= money and costs.get(p.pk, 0) <= points_left
                   and per_team[p.team_id] - (1 if p.team_id == out.team_id else 0) < rules.MAX_PER_TEAM
                   and value(p) > value(out)]
        if not options:
            continue
        pick = rng.choice(sorted(options, key=value, reverse=True)[:5])
        outs.append(out)
        ins.append(pick)
        budget = money - pick.price
        points_left -= costs.get(pick.pk, 0)
        per_team[out.team_id] -= 1
        per_team[pick.team_id] += 1
    if not outs:
        raise FantasyError("No change fits those points and your budget right now")
    return [{"out": o, "in": i, "cost": costs.get(i.pk, rules.MAX_TRANSFER_COST)} for o, i in zip(outs, ins)]
