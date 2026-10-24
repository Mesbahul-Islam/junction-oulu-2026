"""Season-long fantasy Liiga (Fantasy Premier League style, for Finnish ice hockey).

Free to play: no entry fees, no prizes, no virtual points wallet. Users build a
15-player squad under a budget, pick 11 starters and a captain each gameweek,
make transfers, and compete on daily / gameweek / season leaderboards that can
be scoped Finland-wide, to a community (e.g. Oulu) or to a private league.

Data comes from the Liiga stats API (see services/liiga.py). Liiga's own
`gameWeek` numbering is used for gameweeks.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel

PRICE = {"max_digits": 5, "decimal_places": 1}
POINTS = {"max_digits": 8, "decimal_places": 1}
ZERO = Decimal("0")


class Position(models.TextChoices):
    GOALIE = "G", "Goalie"
    DEFENCE = "D", "Defence"
    FORWARD = "F", "Forward"


class Season(TimeStampedModel):
    liiga_season = models.PositiveIntegerField(unique=True)  # Liiga numbering: 2027 = 2026-27
    name = models.CharField(max_length=32)
    is_current = models.BooleanField(default=False, db_index=True)
    budget = models.DecimalField(**PRICE, default=Decimal("100.0"))

    class Meta:
        ordering = ["-liiga_season"]

    def __str__(self):
        return self.name


class Team(TimeStampedModel):
    liiga_id = models.CharField(max_length=64, unique=True)  # e.g. "1368624751:k-espoo"
    name = models.CharField(max_length=64)
    abbreviation = models.CharField(max_length=8, blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    # Local leaderboards / "my team" content, e.g. Kärpät -> Oulu.
    community = models.ForeignKey(
        "communities.CommunityGroup", null=True, blank=True, on_delete=models.SET_NULL, related_name="fantasy_teams"
    )

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Gameweek(TimeStampedModel):
    class Status(models.TextChoices):
        UPCOMING = "upcoming", "Upcoming"
        LIVE = "live", "Live"
        FINISHED = "finished", "Finished"

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="gameweeks")
    number = models.PositiveSmallIntegerField()
    # Lineups and transfers lock at the first puck drop of the gameweek.
    deadline = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UPCOMING, db_index=True)

    class Meta:
        ordering = ["season", "number"]
        constraints = [models.UniqueConstraint(fields=["season", "number"], name="uniq_gameweek_number")]

    def __str__(self):
        return f"{self.season} GW{self.number}"


class Fixture(TimeStampedModel):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        LIVE = "live", "Live"
        FINISHED = "finished", "Finished"

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="fixtures")
    gameweek = models.ForeignKey(Gameweek, null=True, blank=True, on_delete=models.SET_NULL, related_name="fixtures")
    liiga_id = models.PositiveIntegerField()
    serie = models.CharField(max_length=24, blank=True)  # RUNKOSARJA (regular season), PLAYOFFS, ...
    home = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_fixtures")
    away = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_fixtures")
    starts_at = models.DateTimeField(db_index=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    home_goals = models.PositiveSmallIntegerField(null=True, blank=True)
    away_goals = models.PositiveSmallIntegerField(null=True, blank=True)
    finished_type = models.CharField(max_length=48, blank=True)  # e.g. ENDED_DURING_OVERTIME
    stats_synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["starts_at", "liiga_id"]
        constraints = [models.UniqueConstraint(fields=["season", "liiga_id"], name="uniq_fixture_per_season")]

    def __str__(self):
        return f"{self.home} vs {self.away} ({self.starts_at:%Y-%m-%d})"


class Player(TimeStampedModel):
    liiga_id = models.PositiveIntegerField(unique=True)
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.SET_NULL, related_name="players")
    position = models.CharField(max_length=1, choices=Position.choices)
    liiga_role = models.CharField(max_length=32, blank=True)  # raw Liiga role, e.g. LEFT_DEFENSEMAN
    jersey = models.PositiveSmallIntegerField(null=True, blank=True)
    nationality = models.CharField(max_length=3, blank=True)
    picture_url = models.URLField(max_length=500, blank=True)
    price = models.DecimalField(**PRICE, default=Decimal("5.0"))
    injured = models.BooleanField(default=False)
    suspended = models.BooleanField(default=False)
    active = models.BooleanField(default=True)  # False once removed from the team roster
    total_points = models.DecimalField(**POINTS, default=ZERO)  # denormalised, current season
    desk_checked_at = models.DateTimeField(null=True, blank=True)  # last sports desk visit

    class Meta:
        ordering = ["-total_points", "last_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def name(self):
        return f"{self.first_name} {self.last_name}"


class PlayerGameStat(TimeStampedModel):
    """One player's box score in one fixture, with the fantasy points it earned."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="game_stats")
    fixture = models.ForeignKey(Fixture, on_delete=models.CASCADE, related_name="player_stats")
    stats = models.JSONField(default=dict, blank=True)
    breakdown = models.JSONField(default=dict, blank=True)  # {"goals": 8, "assists": 3, ...}
    points = models.DecimalField(**POINTS, default=ZERO)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["player", "fixture"], name="uniq_player_game_stat")]


class Squad(TimeStampedModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="fantasy_squads")
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="squads")
    name = models.CharField(max_length=60)
    bank = models.DecimalField(**PRICE, default=ZERO)
    free_transfers = models.PositiveSmallIntegerField(default=1)
    # Changes before this gameweek's deadline are free (squad building).
    first_gameweek = models.ForeignKey(Gameweek, on_delete=models.PROTECT, related_name="+")
    total_points = models.DecimalField(**POINTS, default=ZERO)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "season"], name="uniq_squad_per_season")]

    def __str__(self):
        return self.name


class SquadPick(TimeStampedModel):
    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name="picks")
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="squad_picks")
    purchase_price = models.DecimalField(**PRICE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["squad", "player"], name="uniq_squad_player")]


class Lineup(TimeStampedModel):
    """Starters, bench order and captaincy for one gameweek.

    If a user doesn't set a lineup, their previous one is carried forward when
    the gameweek is scored.
    """

    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name="lineups")
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name="lineups")
    captain = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="+")
    vice_captain = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["squad", "gameweek"], name="uniq_lineup_per_gameweek")]


class LineupSlot(models.Model):
    """slot 1..11 are starters; 12..15 the bench in auto-substitution order."""

    lineup = models.ForeignKey(Lineup, on_delete=models.CASCADE, related_name="slots")
    player = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="+")
    slot = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["slot"]
        constraints = [
            models.UniqueConstraint(fields=["lineup", "slot"], name="uniq_lineup_slot"),
            models.UniqueConstraint(fields=["lineup", "player"], name="uniq_lineup_player"),
        ]

    @property
    def is_starter(self):
        return self.slot <= 11


class Transfer(TimeStampedModel):
    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name="transfers")
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name="transfers")
    player_out = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="+")
    player_in = models.ForeignKey(Player, on_delete=models.PROTECT, related_name="+")
    price_out = models.DecimalField(**PRICE)
    price_in = models.DecimalField(**PRICE)
    point_cost = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]


class GameweekScore(TimeStampedModel):
    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name="gameweek_scores")
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name="scores")
    points = models.DecimalField(**POINTS, default=ZERO)  # lineup points incl. captain bonus
    transfer_cost = models.PositiveSmallIntegerField(default=0)
    total = models.DecimalField(**POINTS, default=ZERO)  # points - transfer_cost
    # Per-player detail: [{"player": id, "points": x, "multiplier": 2, "auto_sub": false}, ...]
    detail = models.JSONField(default=list, blank=True)
    final = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["squad", "gameweek"], name="uniq_gameweek_score")]


class DailyScore(TimeStampedModel):
    """Points a squad earned from fixtures played on one calendar day (Finnish time)."""

    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name="daily_scores")
    gameweek = models.ForeignKey(Gameweek, on_delete=models.CASCADE, related_name="daily_scores")
    date = models.DateField(db_index=True)
    points = models.DecimalField(**POINTS, default=ZERO)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["squad", "date"], name="uniq_daily_score")]


class League(TimeStampedModel):
    """Private league ("kimppa") among friends, joined with an invite code."""

    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="leagues")
    name = models.CharField(max_length=60)
    code = models.CharField(max_length=12, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_fantasy_leagues")
    members = models.ManyToManyField(Squad, related_name="leagues", blank=True)

    def __str__(self):
        return self.name


# --------------------------------------------------------------------------- brand partners

class Sponsor(TimeStampedModel):
    """A brand that funds prizes. Its logo is a file under MEDIA_ROOT (see services/rewards.py)."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(unique=True)
    logo = models.CharField(max_length=200, blank=True)  # path under MEDIA_ROOT, e.g. fantasy/brands/prisma.webp
    tagline = models.CharField(max_length=140, blank=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return self.name


class Reward(TimeStampedModel):
    """A sponsored prize for a leaderboard position, e.g. Prisma's gift card for 1st place each gameweek."""

    class Period(models.TextChoices):
        WEEK = "week", "Every gameweek"
        SEASON = "season", "End of season"

    class Scope(models.TextChoices):
        GLOBAL = "global", "Finland"
        COMMUNITY = "community", "Community"

    class Kind(models.TextChoices):
        RANK = "rank", "Leaderboard place (top 3)"
        PLAYER = "player", "Your pick scores"
        POINTS = "points", "Points target"
        TIER = "tier", "Season tier"

    sponsor = models.ForeignKey(Sponsor, on_delete=models.CASCADE, related_name="rewards")
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.RANK)
    # PLAYER: the brand's player; you win if he is in your lineup and scores at least `threshold` points.
    player = models.ForeignKey(Player, null=True, blank=True, on_delete=models.SET_NULL, related_name="rewards")
    # PLAYER and POINTS: fantasy points needed in the gameweek.
    threshold = models.PositiveSmallIntegerField(null=True, blank=True)
    # TIER: lowest season tier that wins ("gold" means gold or diamond).
    tier = models.CharField(max_length=8, blank=True)
    season = models.ForeignKey(Season, on_delete=models.CASCADE, related_name="rewards")
    title = models.CharField(max_length=80)  # what you get, e.g. "50 € gift card"
    description = models.CharField(max_length=200, blank=True)
    title_fi = models.CharField(max_length=80, blank=True)  # Finnish versions for Finnish readers
    description_fi = models.CharField(max_length=200, blank=True)
    period = models.CharField(max_length=8, choices=Period.choices, default=Period.WEEK)
    scope = models.CharField(max_length=10, choices=Scope.choices, default=Scope.GLOBAL)
    community_slug = models.SlugField(blank=True)  # for community scope, e.g. "oulu"
    rank_from = models.PositiveSmallIntegerField(default=1)
    rank_to = models.PositiveSmallIntegerField(default=1)
    voucher_days = models.PositiveSmallIntegerField(default=30)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["period", "scope", "rank_from"]

    def __str__(self):
        return f"{self.sponsor}: {self.title} (#{self.rank_from}-{self.rank_to}, {self.period})"


class Voucher(TimeStampedModel):
    """A prize won: one per reward, squad and gameweek."""

    reward = models.ForeignKey(Reward, on_delete=models.CASCADE, related_name="vouchers")
    squad = models.ForeignKey(Squad, on_delete=models.CASCADE, related_name="vouchers")
    gameweek = models.ForeignKey(Gameweek, null=True, blank=True, on_delete=models.CASCADE, related_name="vouchers")
    rank = models.PositiveSmallIntegerField()
    code = models.CharField(max_length=32, unique=True)
    expires_at = models.DateTimeField()
    redeemed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["reward", "squad", "gameweek"], name="uniq_voucher_per_win")]


# --------------------------------------------------------------------------- sports desk (background agent)

class PlayerNote(TimeStampedModel):
    """Something the sports desk agent found about a player: recent form from the Liiga game log,
    a status change, or a Kaleva story that mentions him."""

    class Kind(models.TextChoices):
        FORM = "form", "Form"
        STATUS = "status", "Status"
        NEWS = "news", "News"

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="notes")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    key = models.CharField(max_length=300)  # dedupe: the story URL, or "form" (updated in place)
    title = models.CharField(max_length=300)
    body = models.TextField(blank=True)
    url = models.URLField(max_length=500, blank=True)
    source = models.CharField(max_length=20)  # "liiga" or "kaleva"
    wording = models.CharField(max_length=4, default="data")  # "ai" when reworded (numbers checked)
    published_at = models.DateTimeField(null=True, blank=True)
    # Form notes keep their numbers, so the text can be written in the reader's language.
    facts = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-published_at", "-updated_at"]
        constraints = [models.UniqueConstraint(fields=["player", "key"], name="uniq_player_note")]


class Report(TimeStampedModel):
    """A precomputed match analysis or coach report, so the app reads it instead of waiting."""

    key = models.CharField(max_length=80, unique=True)  # e.g. "match:123:full", "coach:45"
    data = models.JSONField(default=dict)
    wording = models.CharField(max_length=4, default="data")
