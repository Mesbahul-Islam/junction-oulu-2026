"""FR-5 sports prediction markets and fantasy contests.

VIRTUAL POINTS ONLY. Every amount in this app is a non-redeemable virtual
point balance used for engagement. There are no real-money deposits, no cash
withdrawals and no cash payouts; points cannot be bought or exchanged for
money or goods.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from apps.common.models import TimeStampedModel

POINTS = {"max_digits": 14, "decimal_places": 2}
ZERO = Decimal("0.00")
ONE = Decimal("1.00")
MIN_PRICE = Decimal("0.01")


class Sport(models.TextChoices):
    ICE_HOCKEY = "ice_hockey", "Ice hockey"
    FOOTBALL = "football", "Football"
    FLOORBALL = "floorball", "Floorball"
    PESAPALLO = "pesapallo", "Pesäpallo"


class SportEvent(TimeStampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        FINISHED = "finished", "Finished"
        CANCELLED = "cancelled", "Cancelled"

    sport = models.CharField(max_length=32, choices=Sport.choices, default=Sport.ICE_HOCKEY)
    league = models.CharField(max_length=64, blank=True)
    home = models.CharField(max_length=128)
    away = models.CharField(max_length=128)
    starts_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SCHEDULED)
    # e.g. {"home": 3, "away": 2, "period_scores": [...], "player_stats": {...}}
    final_score = models.JSONField(null=True, blank=True)
    external_id = models.CharField(max_length=128, blank=True, db_index=True)

    class Meta:
        ordering = ["starts_at"]

    def __str__(self):
        return f"{self.home} vs. {self.away} ({self.starts_at:%Y-%m-%d})"


class EventMarket(TimeStampedModel):
    """A market on an event: binary yes/no (Kalshi-style) or a fantasy contest (Dream11-style)."""

    class Kind(models.TextChoices):
        BINARY = "binary", "Binary"
        FANTASY = "fantasy", "Fantasy"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        LOCKED = "locked", "Locked"
        RESOLVED = "resolved", "Resolved"
        VOID = "void", "Void"

    class Resolution(models.TextChoices):
        YES = "yes", "Yes"
        NO = "no", "No"

    class Rule(models.TextChoices):
        """How a binary market auto-resolves from the final score."""

        MANUAL = "manual", "Manual (admin resolves)"
        HOME_WIN = "home_win", "Home team wins"
        AWAY_WIN = "away_win", "Away team wins"
        TOTAL_OVER = "total_over", "Total goals over line"

    event = models.ForeignKey(SportEvent, on_delete=models.CASCADE, related_name="markets")
    kind = models.CharField(max_length=16, choices=Kind.choices, default=Kind.BINARY)
    question = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN, db_index=True)
    resolution = models.CharField(max_length=8, choices=Resolution.choices, null=True, blank=True)
    rule = models.CharField(max_length=16, choices=Rule.choices, default=Rule.MANUAL)
    line = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.question


class Player(TimeStampedModel):
    class PositionCode(models.TextChoices):
        FORWARD = "F", "Forward"
        DEFENCE = "D", "Defence"
        GOALIE = "G", "Goalie"
        OTHER = "X", "Other"

    name = models.CharField(max_length=128)
    team = models.CharField(max_length=128, db_index=True)
    sport = models.CharField(max_length=32, choices=Sport.choices, default=Sport.ICE_HOCKEY)
    salary = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(ZERO)])
    position = models.CharField(max_length=2, choices=PositionCode.choices, default=PositionCode.FORWARD)
    external_id = models.CharField(max_length=128, blank=True, db_index=True)

    class Meta:
        ordering = ["team", "name"]

    def __str__(self):
        return f"{self.name} ({self.team}, {self.position})"


class FantasyContest(TimeStampedModel):
    """Virtual-points fantasy contest. Entry fees and prizes are virtual points only."""

    market = models.OneToOneField(EventMarket, on_delete=models.CASCADE, related_name="contest")
    salary_cap = models.DecimalField(max_digits=10, decimal_places=2)
    roster_size = models.PositiveSmallIntegerField(default=6)
    entry_fee = models.DecimalField(**POINTS, default=Decimal("50.00"), validators=[MinValueValidator(ZERO)])
    # Fractions of the prize pool for rank 1..N, e.g. [0.5, 0.3, 0.2].
    prize_structure = models.JSONField(default=list, blank=True)
    player_pool = models.ManyToManyField(Player, related_name="contests", blank=True)

    def __str__(self):
        return f"Fantasy: {self.market.event}"


class FantasyEntry(TimeStampedModel):
    contest = models.ForeignKey(FantasyContest, on_delete=models.CASCADE, related_name="entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fantasy_entries")
    players = models.ManyToManyField(Player, related_name="fantasy_entries")
    points = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)
    rank = models.PositiveIntegerField(null=True, blank=True)
    payout = models.DecimalField(**POINTS, default=ZERO)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["contest", "user"], name="uniq_fantasy_entry_per_user")]
        ordering = ["-points", "created_at"]


class Position(TimeStampedModel):
    """A binary-market position. stake = price * quantity (virtual points); a win pays quantity * 1.00."""

    class Side(models.TextChoices):
        YES = "yes", "Yes"
        NO = "no", "No"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        WON = "won", "Won"
        LOST = "lost", "Lost"
        VOID = "void", "Void"

    market = models.ForeignKey(EventMarket, on_delete=models.CASCADE, related_name="positions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="market_positions")
    side = models.CharField(max_length=3, choices=Side.choices)
    price = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(MIN_PRICE), MaxValueValidator(ONE)],
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    stake = models.DecimalField(**POINTS)
    payout = models.DecimalField(**POINTS, default=ZERO)
    status = models.CharField(max_length=8, choices=Status.choices, default=Status.OPEN, db_index=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=MIN_PRICE) & Q(price__lte=ONE), name="position_price_range"
            ),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="position_quantity_positive"),
        ]


class PlayerStat(TimeStampedModel):
    event = models.ForeignKey(SportEvent, on_delete=models.CASCADE, related_name="player_stats")
    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="stats")
    stats = models.JSONField(default=dict, blank=True)
    points = models.DecimalField(max_digits=10, decimal_places=2, default=ZERO)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["event", "player"], name="uniq_player_stat_per_event")]


class Wallet(TimeStampedModel):
    """Virtual points wallet. Not money: no deposits, withdrawals or cash-out.

    `balance` is spendable points and always equals the sum of this wallet's
    LedgerEntry amounts. `locked` is an informational counter of points the
    user currently has at stake in open positions / contest entries (those
    points have already moved to the house wallet). The single house wallet
    (`is_house=True`, no user) is the counterparty of every transaction and
    may go negative (it is the issuer of points).
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet", null=True, blank=True
    )
    is_house = models.BooleanField(default=False)
    balance = models.DecimalField(**POINTS, default=ZERO)
    locked = models.DecimalField(**POINTS, default=ZERO)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["is_house"], condition=Q(is_house=True), name="single_house_wallet"),
            models.CheckConstraint(
                condition=Q(is_house=True) | Q(user__isnull=False), name="wallet_user_unless_house"
            ),
        ]

    def __str__(self):
        return "HOUSE" if self.is_house else f"Wallet<{self.user_id}>"


class LedgerEntry(TimeStampedModel):
    """Double-entry ledger leg. Amounts of all legs sharing a transaction_id sum to 0."""

    class Kind(models.TextChoices):
        GRANT = "grant", "Signup grant"
        STAKE_LOCK = "stake_lock", "Stake lock"
        STAKE_RELEASE = "stake_release", "Stake release (refund)"
        PAYOUT = "payout", "Payout"
        FEE = "fee", "Fee"

    transaction_id = models.UUIDField(db_index=True)
    wallet = models.ForeignKey(Wallet, on_delete=models.PROTECT, related_name="entries")
    amount = models.DecimalField(**POINTS)  # signed
    kind = models.CharField(max_length=16, choices=Kind.choices)
    ref = models.CharField(max_length=128, blank=True, db_index=True)  # e.g. "position:12"
    memo = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name_plural = "ledger entries"
