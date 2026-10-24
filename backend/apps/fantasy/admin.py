from django.contrib import admin

from .models import Fixture, Gameweek, GameweekScore, League, Lineup, LineupSlot, Player, Season, Squad, SquadPick, Team, Transfer


@admin.register(Season)
class SeasonAdmin(admin.ModelAdmin):
    list_display = ["name", "liiga_season", "is_current", "budget"]


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ["name", "abbreviation", "liiga_id", "community"]


@admin.register(Gameweek)
class GameweekAdmin(admin.ModelAdmin):
    list_display = ["season", "number", "deadline", "status"]
    list_filter = ["season", "status"]


@admin.register(Fixture)
class FixtureAdmin(admin.ModelAdmin):
    list_display = ["__str__", "gameweek", "status", "home_goals", "away_goals", "stats_synced_at"]
    list_filter = ["season", "status", "serie"]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["__str__", "team", "position", "price", "total_points", "injured", "active"]
    list_filter = ["position", "team", "injured", "active"]
    search_fields = ["first_name", "last_name"]
    list_editable = ["price"]


class SquadPickInline(admin.TabularInline):
    model = SquadPick
    extra = 0
    raw_id_fields = ["player"]


@admin.register(Squad)
class SquadAdmin(admin.ModelAdmin):
    list_display = ["name", "user", "season", "total_points", "bank", "free_transfers"]
    inlines = [SquadPickInline]


class LineupSlotInline(admin.TabularInline):
    model = LineupSlot
    extra = 0
    raw_id_fields = ["player"]


@admin.register(Lineup)
class LineupAdmin(admin.ModelAdmin):
    list_display = ["squad", "gameweek", "captain", "vice_captain"]
    inlines = [LineupSlotInline]


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ["squad", "gameweek", "player_out", "player_in", "point_cost"]


@admin.register(GameweekScore)
class GameweekScoreAdmin(admin.ModelAdmin):
    list_display = ["squad", "gameweek", "points", "transfer_cost", "total", "final"]


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "season", "owner"]
