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
