from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.test import override_settings
from django.utils import timezone

from apps.markets.models import EventMarket, FantasyContest, LedgerEntry, Player, Position, SportEvent, Wallet
from apps.markets.services.ledger import (
    InsufficientBalance,
    Leg,
    UnbalancedTransaction,
    get_house_wallet,
    get_or_create_wallet,
    post_transaction,
)
from apps.markets.services.settlement import ingest_final_score, resolve_binary, settle_fantasy
from apps.markets.services.trading import enter_fantasy_contest, place_binary_order

D = Decimal


def make_user(django_user_model, n):
    return django_user_model.objects.create_user(email=f"u{n}@example.com", password="x-pass-123")


def assert_invariants():
    # Every transaction balances, global sum is zero, and each wallet balance equals its ledger sum.
    assert (LedgerEntry.objects.aggregate(s=Sum("amount"))["s"] or D(0)) == D(0)
    for tx in LedgerEntry.objects.values_list("transaction_id", flat=True).distinct():
        assert LedgerEntry.objects.filter(transaction_id=tx).aggregate(s=Sum("amount"))["s"] == D(0)
    for w in Wallet.objects.all():
        assert w.balance == (w.entries.aggregate(s=Sum("amount"))["s"] or D(0))
        if not w.is_house:
            assert w.balance >= 0


@pytest.fixture
def event():
    return SportEvent.objects.create(home="Kärpät", away="Tappara", league="Liiga",
                                     starts_at=timezone.now() + timedelta(days=1))


@pytest.fixture
def market(event):
    return EventMarket.objects.create(event=event, question="Kärpät win?", rule=EventMarket.Rule.HOME_WIN)


@pytest.mark.django_db
@override_settings(MARKETS_SIGNUP_GRANT=1000)
def test_signup_grant_is_balanced_and_idempotent(django_user_model):
    user = make_user(django_user_model, 1)
    w1 = get_or_create_wallet(user)
    w2 = get_or_create_wallet(user)
    assert w1.pk == w2.pk
    assert w1.balance == D("1000.00")
    assert get_house_wallet().balance == D("-1000.00")
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.GRANT).count() == 2
    assert_invariants()


@pytest.mark.django_db
def test_unbalanced_transaction_rejected(django_user_model):
    wallet = get_or_create_wallet(make_user(django_user_model, 1))
    before = LedgerEntry.objects.count()
    with pytest.raises(UnbalancedTransaction):
        post_transaction([Leg(wallet, D("5"), LedgerEntry.Kind.FEE), Leg(get_house_wallet(), D("-4"), "fee")])
    assert LedgerEntry.objects.count() == before
    assert_invariants()


@pytest.mark.django_db
@override_settings(MARKETS_SIGNUP_GRANT=100)
def test_insufficient_balance_rolls_back(django_user_model, market):
    user = make_user(django_user_model, 1)
    with pytest.raises(InsufficientBalance):
        place_binary_order(user, market, "yes", D("0.60"), 200)  # stake 120 > 100
    assert Position.objects.count() == 0
    wallet = Wallet.objects.get(user=user)
    assert wallet.balance == D("100.00") and wallet.locked == D("0.00")
    assert_invariants()


@pytest.mark.django_db
@override_settings(MARKETS_SIGNUP_GRANT=1000)
def test_binary_settlement_pays_winners_and_is_idempotent(django_user_model, market):
    yes_user, no_user = make_user(django_user_model, 1), make_user(django_user_model, 2)
    p_yes = place_binary_order(yes_user, market, "yes", D("0.40"), 100)  # stake 40
    p_no = place_binary_order(no_user, market, "no", D("0.60"), 100)  # stake 60
    assert p_yes.stake == D("40.00") and p_no.stake == D("60.00")

    yes_wallet = Wallet.objects.get(user=yes_user)
    assert yes_wallet.balance == D("960.00") and yes_wallet.locked == D("40.00")
    assert_invariants()

    resolve_binary(market, "yes")
    resolve_binary(market, "yes")  # idempotent

    yes_wallet.refresh_from_db()
    no_wallet = Wallet.objects.get(user=no_user)
    assert yes_wallet.balance == D("1060.00") and yes_wallet.locked == D("0.00")
    assert no_wallet.balance == D("940.00") and no_wallet.locked == D("0.00")
    assert LedgerEntry.objects.filter(kind=LedgerEntry.Kind.PAYOUT).count() == 2  # one tx, 2 legs
    p_yes.refresh_from_db(); p_no.refresh_from_db()
    assert p_yes.status == Position.Status.WON and p_yes.payout == D("100.00")
    assert p_no.status == Position.Status.LOST
    market.refresh_from_db()
    assert market.status == EventMarket.Status.RESOLVED and market.resolution == "yes"
    assert_invariants()

    with pytest.raises(Exception):
        resolve_binary(market, "no")


@pytest.mark.django_db
@override_settings(MARKETS_SIGNUP_GRANT=1000)
def test_price_validation(django_user_model, market):
    user = make_user(django_user_model, 1)
    for bad in (D("0"), D("1.01"), D("0.005")):
        with pytest.raises(Exception):
            place_binary_order(user, market, "yes", bad, 1)
    assert Position.objects.count() == 0


@pytest.mark.django_db
@override_settings(MARKETS_SIGNUP_GRANT=1000)
def test_final_score_ingestion_settles_binary_and_fantasy(django_user_model, event, market):
    players = [Player.objects.create(name=f"P{i}", team="Kärpät", salary=D("5")) for i in range(4)]
    fmarket = EventMarket.objects.create(event=event, kind=EventMarket.Kind.FANTASY, question="Fantasy")
    contest = FantasyContest.objects.create(market=fmarket, salary_cap=D("10"), roster_size=2,
                                            entry_fee=D("50"), prize_structure=[1.0])
    contest.player_pool.set(players)
    a, b = make_user(django_user_model, 1), make_user(django_user_model, 2)
    enter_fantasy_contest(a, contest, [players[0].pk, players[1].pk])
    enter_fantasy_contest(b, contest, [players[2].pk, players[3].pk])
    place_binary_order(a, market, "no", D("0.50"), 10)

    summary = ingest_final_score(event, {
        "home_score": 4, "away_score": 2,
        "player_stats": {str(players[0].pk): {"goals": 2}, str(players[2].pk): {"assists": 1}},
    })
    assert set(summary["resolved"]) == {market.pk, fmarket.pk}
    wa, wb = Wallet.objects.get(user=a), Wallet.objects.get(user=b)
    # a: 1000 - 50 fee - 5 stake (lost) + 100 prize; b: 1000 - 50
    assert wa.balance == D("1045.00") and wa.locked == D("0.00")
    assert wb.balance == D("950.00") and wb.locked == D("0.00")
    settle_fantasy(contest)  # idempotent
    assert Wallet.objects.get(user=a).balance == D("1045.00")
    assert_invariants()
