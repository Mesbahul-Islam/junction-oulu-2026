"""Double-entry ledger for VIRTUAL POINTS ONLY.

Points have no cash value: there are no deposits, withdrawals or cash payouts.
Every movement is a balanced transaction (legs sum to exactly 0) with the
house wallet as counterparty. Wallet rows are locked with SELECT ... FOR UPDATE
in ascending primary-key order to avoid deadlocks between concurrent writers.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction

from ..models import ZERO, LedgerEntry, Wallet

CENT = Decimal("0.01")


class MarketError(Exception):
    """Base class for domain errors raised by markets services (mapped to HTTP 400)."""


class InsufficientBalance(MarketError):
    pass


class UnbalancedTransaction(MarketError):
    pass


@dataclass
class Leg:
    wallet: Wallet
    amount: Decimal
    kind: str
    ref: str = ""
    memo: str = ""
    # Change to the wallet's informational `locked` counter (not a ledger amount).
    locked_delta: Decimal = ZERO


def q(value) -> Decimal:
    return Decimal(value).quantize(CENT)


def get_house_wallet() -> Wallet:
    wallet = Wallet.objects.filter(is_house=True).first()
    if wallet:
        return wallet
    try:
        with transaction.atomic():
            return Wallet.objects.create(is_house=True, user=None)
    except IntegrityError:
        return Wallet.objects.get(is_house=True)


def lock_wallets(wallet_ids) -> dict[int, Wallet]:
    """SELECT FOR UPDATE the given wallets in ascending pk order. Must run inside atomic()."""
    ids = sorted(set(wallet_ids))
    return {w.pk: w for w in Wallet.objects.select_for_update().filter(pk__in=ids).order_by("pk")}


def post_transaction(legs: list[Leg]) -> uuid.UUID:
    """Atomically post a balanced set of ledger legs and update wallet balances.

    Raises UnbalancedTransaction if amounts don't sum to 0 and
    InsufficientBalance if a user wallet would go negative.
    """
    if not legs:
        raise UnbalancedTransaction("Empty transaction")
    total = sum((q(leg.amount) for leg in legs), ZERO)
    if total != ZERO:
        raise UnbalancedTransaction(f"Legs sum to {total}, expected 0")

    tx_id = uuid.uuid4()
    with transaction.atomic():
        wallets = lock_wallets(leg.wallet.pk for leg in legs)
        balance_delta: dict[int, Decimal] = defaultdict(lambda: ZERO)
        locked_delta: dict[int, Decimal] = defaultdict(lambda: ZERO)
        for leg in legs:
            balance_delta[leg.wallet.pk] += q(leg.amount)
            locked_delta[leg.wallet.pk] += q(leg.locked_delta)

        for pk in sorted(wallets):
            wallet = wallets[pk]
            new_balance = wallet.balance + balance_delta[pk]
            new_locked = wallet.locked + locked_delta[pk]
            if not wallet.is_house and new_balance < ZERO:
                raise InsufficientBalance(
                    f"Insufficient points: balance {wallet.balance}, needs {-balance_delta[pk]}"
                )
            if new_locked < ZERO:
                new_locked = ZERO
            wallet.balance = new_balance
            wallet.locked = new_locked
            wallet.save(update_fields=["balance", "locked", "updated_at"])

        LedgerEntry.objects.bulk_create(
            [
                LedgerEntry(
                    transaction_id=tx_id,
                    wallet_id=leg.wallet.pk,
                    amount=q(leg.amount),
                    kind=leg.kind,
                    ref=leg.ref,
                    memo=leg.memo,
                )
                for leg in legs
            ]
        )
        # Keep caller-held instances in sync.
        for leg in legs:
            fresh = wallets[leg.wallet.pk]
            leg.wallet.balance, leg.wallet.locked = fresh.balance, fresh.locked
    return tx_id


def transfer(src: Wallet, dst: Wallet, amount, kind: str, ref: str = "", memo: str = "",
             src_locked_delta=ZERO, dst_locked_delta=ZERO) -> uuid.UUID:
    amount = q(amount)
    return post_transaction(
        [
            Leg(src, -amount, kind, ref, memo, locked_delta=q(src_locked_delta)),
            Leg(dst, amount, kind, ref, memo, locked_delta=q(dst_locked_delta)),
        ]
    )


def adjust_locked(wallet: Wallet, delta) -> None:
    """Change only the informational `locked` counter (e.g. a lost stake leaves escrow)."""
    with transaction.atomic():
        locked = lock_wallets([wallet.pk])[wallet.pk]
        locked.locked = max(ZERO, locked.locked + q(delta))
        locked.save(update_fields=["locked", "updated_at"])
        wallet.locked = locked.locked


def get_or_create_wallet(user) -> Wallet:
    """Return the user's wallet, creating it with the virtual-points signup grant."""
    wallet = Wallet.objects.filter(user=user).first()
    if wallet:
        return wallet
    house = get_house_wallet()
    try:
        with transaction.atomic():
            wallet = Wallet.objects.create(user=user)
            grant = q(getattr(settings, "MARKETS_SIGNUP_GRANT", 1000))
            if grant > ZERO:
                transfer(house, wallet, grant, LedgerEntry.Kind.GRANT, ref=f"user:{user.pk}",
                         memo="Signup grant (virtual points)")
    except IntegrityError:
        wallet = Wallet.objects.get(user=user)
    return wallet
