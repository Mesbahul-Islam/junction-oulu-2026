"""Settlement of binary markets and fantasy contests. VIRTUAL POINTS ONLY.

Payouts are virtual points credited from the house wallet; nothing here is
redeemable for cash. All settlement functions are idempotent: re-running them
on an already-settled market is a no-op.
"""

from __future__ import annotations

import logging
from decimal import ROUND_DOWN, Decimal

from django.db import transaction
from django.utils import timezone

from ..models import (
    ONE,
    ZERO,
    EventMarket,
    FantasyContest,
    FantasyEntry,
    LedgerEntry,
    Player,
    PlayerStat,
    Position,
    SportEvent,
    Wallet,
)
from .ledger import MarketError, adjust_locked, get_house_wallet, lock_wallets, q, transfer

logger = logging.getLogger(__name__)

# Fantasy scoring for ice hockey (per stat unit).
HOCKEY_SCORING: dict[str, Decimal] = {
    "goals": Decimal("3"),
    "assists": Decimal("2"),
    "shots": Decimal("0.5"),
    "plus_minus": Decimal("1"),
    "blocks": Decimal("0.5"),
    "hits": Decimal("0.25"),
    "penalty_minutes": Decimal("-0.25"),
    "saves": Decimal("0.2"),
    "goals_against": Decimal("-1"),
    "win": Decimal("3"),
    "shutout": Decimal("3"),
}
DEFAULT_PRIZE_STRUCTURE = [Decimal("0.5"), Decimal("0.3"), Decimal("0.2")]
SETTLED = (EventMarket.Status.RESOLVED, EventMarket.Status.VOID)


def fantasy_points(stats: dict, scoring: dict[str, Decimal] = HOCKEY_SCORING) -> Decimal:
    total = ZERO
    for key, weight in scoring.items():
        value = stats.get(key)
        if value in (None, ""):
            continue
        total += Decimal(str(value)) * weight
    return q(total)


def _user_wallets(user_ids) -> dict[int, Wallet]:
    return {w.user_id: w for w in Wallet.objects.filter(user_id__in=set(user_ids))}


# --------------------------------------------------------------------------- binary


def resolve_binary(market: EventMarket, resolution: str) -> EventMarket:
    """Resolve a binary market. Winners receive quantity * 1.00 from the house; losers'
    stakes (already in the house wallet) stay there. Idempotent."""
    if resolution not in EventMarket.Resolution.values:
        raise MarketError("resolution must be 'yes' or 'no'")
    house = get_house_wallet()
    with transaction.atomic():
        market = EventMarket.objects.select_for_update().get(pk=market.pk)
        if market.kind != EventMarket.Kind.BINARY:
            raise MarketError("Not a binary market")
        if market.status == EventMarket.Status.RESOLVED:
            if market.resolution == resolution:
                return market
            raise MarketError(f"Market already resolved as {market.resolution}")
        if market.status == EventMarket.Status.VOID:
            raise MarketError("Market is void")

        positions = list(market.positions.select_for_update().filter(status=Position.Status.OPEN))
        wallets = _user_wallets(p.user_id for p in positions)
        lock_wallets([house.pk, *(w.pk for w in wallets.values())])

        for p in positions:
            wallet = wallets[p.user_id]
            if p.side == resolution:
                payout = q(Decimal(p.quantity) * ONE)
                transfer(house, wallet, payout, LedgerEntry.Kind.PAYOUT, ref=f"position:{p.pk}",
                         memo=f"Won {p.side.upper()} x{p.quantity}", dst_locked_delta=-p.stake)
                p.status, p.payout = Position.Status.WON, payout
            else:
                adjust_locked(wallet, -p.stake)
                p.status, p.payout = Position.Status.LOST, ZERO
            p.save(update_fields=["status", "payout", "updated_at"])

        market.status = EventMarket.Status.RESOLVED
        market.resolution = resolution
        market.resolved_at = timezone.now()
        market.save(update_fields=["status", "resolution", "resolved_at", "updated_at"])
    return market


def void_market(market: EventMarket) -> EventMarket:
    """Void a market and refund every open stake / entry fee. Idempotent."""
    house = get_house_wallet()
    with transaction.atomic():
        market = EventMarket.objects.select_for_update().get(pk=market.pk)
        if market.status == EventMarket.Status.VOID:
            return market
        if market.status == EventMarket.Status.RESOLVED:
            raise MarketError("Market already resolved")

        refunds: list[tuple[int, Decimal, str, object]] = []  # (user_id, amount, ref, obj)
        if market.kind == EventMarket.Kind.BINARY:
            for p in market.positions.select_for_update().filter(status=Position.Status.OPEN):
                refunds.append((p.user_id, p.stake, f"position:{p.pk}", p))
        else:
            contest = FantasyContest.objects.filter(market=market).first()
            if contest:
                for e in contest.entries.select_for_update().all():
                    refunds.append((e.user_id, q(contest.entry_fee), f"fantasy_entry:{e.pk}", e))
        wallets = _user_wallets(r[0] for r in refunds)
        lock_wallets([house.pk, *(w.pk for w in wallets.values())])

        for user_id, amount, ref, obj in refunds:
            if amount > ZERO:
                transfer(house, wallets[user_id], amount, LedgerEntry.Kind.STAKE_RELEASE, ref=ref,
                         memo="Market void: refund", dst_locked_delta=-amount)
            if isinstance(obj, Position):
                obj.status = Position.Status.VOID
                obj.save(update_fields=["status", "updated_at"])

        market.status = EventMarket.Status.VOID
        market.resolved_at = timezone.now()
        market.save(update_fields=["status", "resolved_at", "updated_at"])
    return market


def binary_resolution_from_score(market: EventMarket, home: int, away: int) -> str | None:
    rule = market.rule
    if rule == EventMarket.Rule.HOME_WIN:
        return "yes" if home > away else "no"
    if rule == EventMarket.Rule.AWAY_WIN:
        return "yes" if away > home else "no"
    if rule == EventMarket.Rule.TOTAL_OVER and market.line is not None:
        return "yes" if Decimal(home + away) > market.line else "no"
    return None  # manual


# --------------------------------------------------------------------------- fantasy


def _normalize_stats(stats) -> dict[int, dict]:
    """Accept {player_id: {...}} or [{"player_id": 1, ...}] / [{"player": "Name", "team": ..., ...}]."""
    out: dict[int, dict] = {}
    if isinstance(stats, dict):
        for key, value in stats.items():
            out[int(key)] = dict(value or {})
        return out
    for row in stats or []:
        row = dict(row)
        pid = row.pop("player_id", None)
        if pid is None and row.get("player"):
            qs = Player.objects.filter(name__iexact=row.pop("player"))
            if row.get("team"):
                qs = qs.filter(team__iexact=row["team"])
            player = qs.first()
            pid = player.pk if player else None
        row.pop("team", None)
        if pid is not None:
            out[int(pid)] = row
    return out


def score_fantasy(contest: FantasyContest, stats) -> list[FantasyEntry]:
    """Store PlayerStat rows for the contest's event and recompute each entry's points."""
    event = contest.market.event
    normalized = _normalize_stats(stats)
    with transaction.atomic():
        player_points: dict[int, Decimal] = {}
        valid_ids = set(Player.objects.filter(pk__in=normalized.keys()).values_list("pk", flat=True))
        for pid, row in normalized.items():
            if pid not in valid_ids:
                continue
            pts = fantasy_points(row)
            PlayerStat.objects.update_or_create(event=event, player_id=pid, defaults={"stats": row, "points": pts})
            player_points[pid] = pts
        # Include previously ingested stats for players not in this payload.
        for ps in PlayerStat.objects.filter(event=event).exclude(player_id__in=player_points.keys()):
            player_points[ps.player_id] = ps.points

        entries = list(contest.entries.prefetch_related("players"))
        for entry in entries:
            entry.points = q(sum((player_points.get(p.pk, ZERO) for p in entry.players.all()), ZERO))
            entry.save(update_fields=["points", "updated_at"])
    return entries


def settle_fantasy(contest: FantasyContest) -> FantasyContest:
    """Rank entries and pay the prize pool (sum of entry fees, virtual points) to the top N. Idempotent."""
    house = get_house_wallet()
    with transaction.atomic():
        market = EventMarket.objects.select_for_update().get(pk=contest.market_id)
        if market.status in SETTLED:
            return contest
        contest = FantasyContest.objects.get(pk=contest.pk)
        entries = list(contest.entries.select_for_update().order_by("-points", "created_at", "pk"))
        fee = q(contest.entry_fee)
        pool = q(fee * len(entries))
        structure = [Decimal(str(f)) for f in (contest.prize_structure or DEFAULT_PRIZE_STRUCTURE)]
        if sum(structure) > ONE:
            raise MarketError("prize_structure fractions exceed 1.0")

        wallets = _user_wallets(e.user_id for e in entries)
        lock_wallets([house.pk, *(w.pk for w in wallets.values())])

        for idx, entry in enumerate(entries):
            entry.rank = idx + 1
            wallet = wallets[entry.user_id]
            payout = ZERO
            if idx < len(structure):
                payout = (pool * structure[idx]).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            if payout > ZERO:
                transfer(house, wallet, payout, LedgerEntry.Kind.PAYOUT, ref=f"fantasy_entry:{entry.pk}",
                         memo=f"Fantasy rank {entry.rank}", dst_locked_delta=-fee)
            elif fee > ZERO:
                adjust_locked(wallet, -fee)
            entry.payout = payout
            entry.save(update_fields=["rank", "payout", "updated_at"])

        market.status = EventMarket.Status.RESOLVED
        market.resolved_at = timezone.now()
        market.save(update_fields=["status", "resolved_at", "updated_at"])
    return contest


# --------------------------------------------------------------------------- events


def settle_event(event: SportEvent) -> dict:
    """Settle every unsettled market of a finished/cancelled event from its stored final_score."""
    summary = {"resolved": [], "voided": [], "manual": []}
    if event.status == SportEvent.Status.CANCELLED:
        for m in event.markets.exclude(status__in=SETTLED):
            void_market(m)
            summary["voided"].append(m.pk)
        return summary
    if event.status != SportEvent.Status.FINISHED or not event.final_score:
        return summary

    home = int(event.final_score.get("home", 0))
    away = int(event.final_score.get("away", 0))
    for m in event.markets.exclude(status__in=SETTLED):
        if m.kind == EventMarket.Kind.BINARY:
            resolution = binary_resolution_from_score(m, home, away)
            if resolution is None:
                summary["manual"].append(m.pk)
                continue
            resolve_binary(m, resolution)
        else:
            contest = FantasyContest.objects.filter(market=m).first()
            if contest is None:
                summary["manual"].append(m.pk)
                continue
            score_fantasy(contest, event.final_score.get("player_stats") or {})
            settle_fantasy(contest)
        summary["resolved"].append(m.pk)
    return summary


def ingest_final_score(event: SportEvent, payload: dict) -> dict:
    """Record a final score and settle the event's markets.

    payload: {"home_score": int, "away_score": int,
              "player_stats": {player_id: {goals, assists, ...}} | [{"player_id"|"player", ...}]}
    """
    try:
        home = int(payload.get("home_score", payload.get("home")))
        away = int(payload.get("away_score", payload.get("away")))
    except (TypeError, ValueError):
        raise MarketError("home_score and away_score are required integers") from None
    player_stats = _normalize_stats(payload.get("player_stats") or {})
    with transaction.atomic():
        event = SportEvent.objects.select_for_update().get(pk=event.pk)
        event.final_score = {
            "home": home,
            "away": away,
            "player_stats": {str(k): v for k, v in player_stats.items()},
            "source": payload.get("source", "manual"),
            "ingested_at": timezone.now().isoformat(),
        }
        event.status = SportEvent.Status.FINISHED
        event.save(update_fields=["final_score", "status", "updated_at"])
        EventMarket.objects.filter(event=event, status=EventMarket.Status.OPEN).update(
            status=EventMarket.Status.LOCKED
        )
    summary = settle_event(event)
    logger.info("Ingested final score for event %s: %s", event.pk, summary)
    return summary
