"""Placing binary orders and entering fantasy contests. VIRTUAL POINTS ONLY.

Stakes and entry fees are virtual points moved from the user's wallet to the
house wallet (escrow) and tracked in the user's `locked` counter until
settlement. No real-money deposits or cash payouts exist.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from ..models import ONE, MIN_PRICE, ZERO, EventMarket, FantasyContest, FantasyEntry, LedgerEntry, Player, Position
from .ledger import MarketError, get_house_wallet, get_or_create_wallet, lock_wallets, q, transfer


def _assert_tradeable(market: EventMarket) -> None:
    if market.status != EventMarket.Status.OPEN:
        raise MarketError(f"Market is {market.status}, not open")
    if market.event.starts_at <= timezone.now():
        raise MarketError("Event has already started")


def place_binary_order(user, market: EventMarket, side: str, price, quantity: int) -> Position:
    """Buy `quantity` contracts of `side` at `price` (0.01–1.00). Stake = price * quantity is locked."""
    if side not in Position.Side.values:
        raise MarketError("side must be 'yes' or 'no'")
    try:
        price = Decimal(str(price))
    except (InvalidOperation, ValueError):
        raise MarketError("Invalid price") from None
    if price != price.quantize(Decimal("0.01")) or not (MIN_PRICE <= price <= ONE):
        raise MarketError("price must be between 0.01 and 1.00 in steps of 0.01")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        raise MarketError("Invalid quantity") from None
    if quantity < 1:
        raise MarketError("quantity must be >= 1")

    wallet = get_or_create_wallet(user)
    house = get_house_wallet()
    with transaction.atomic():
        market = EventMarket.objects.select_for_update().select_related("event").get(pk=market.pk)
        if market.kind != EventMarket.Kind.BINARY:
            raise MarketError("Not a binary market")
        _assert_tradeable(market)
        lock_wallets([wallet.pk, house.pk])
        stake = q(price * quantity)
        position = Position.objects.create(
            market=market, user=user, side=side, price=price, quantity=quantity, stake=stake
        )
        transfer(wallet, house, stake, LedgerEntry.Kind.STAKE_LOCK, ref=f"position:{position.pk}",
                 memo=f"{side.upper()} x{quantity} @ {price}", src_locked_delta=stake)
    return position


def enter_fantasy_contest(user, contest: FantasyContest, player_ids) -> FantasyEntry:
    """Enter a contest with a roster. Validates roster size, salary cap and pool; locks entry fee."""
    try:
        ids = [int(p) for p in player_ids]
    except (TypeError, ValueError):
        raise MarketError("player_ids must be a list of integers") from None
    if len(set(ids)) != len(ids):
        raise MarketError("Duplicate players in roster")

    wallet = get_or_create_wallet(user)
    house = get_house_wallet()
    with transaction.atomic():
        contest = FantasyContest.objects.select_related("market__event").get(pk=contest.pk)
        market = EventMarket.objects.select_for_update().select_related("event").get(pk=contest.market_id)
        if market.kind != EventMarket.Kind.FANTASY:
            raise MarketError("Not a fantasy market")
        _assert_tradeable(market)
        if len(ids) != contest.roster_size:
            raise MarketError(f"Roster must have exactly {contest.roster_size} players")

        pool = contest.player_pool.all()
        players = list((pool if pool.exists() else Player.objects).filter(pk__in=ids))
        if len(players) != len(ids):
            raise MarketError("One or more players are not eligible for this contest")
        total_salary = sum((p.salary for p in players), ZERO)
        if total_salary > contest.salary_cap:
            raise MarketError(f"Salary {total_salary} exceeds cap {contest.salary_cap}")
        if FantasyEntry.objects.filter(contest=contest, user=user).exists():
            raise MarketError("Already entered this contest")

        lock_wallets([wallet.pk, house.pk])
        entry = FantasyEntry.objects.create(contest=contest, user=user)
        entry.players.set(players)
        fee = q(contest.entry_fee)
        if fee > ZERO:
            transfer(wallet, house, fee, LedgerEntry.Kind.STAKE_LOCK, ref=f"fantasy_entry:{entry.pk}",
                     memo="Fantasy entry fee (virtual points)", src_locked_delta=fee)
    return entry
