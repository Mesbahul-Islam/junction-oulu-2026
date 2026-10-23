from django.contrib import admin

from .models import (
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


class EventMarketInline(admin.TabularInline):
    model = EventMarket
    extra = 0
    fields = ["kind", "question", "status", "resolution", "rule", "line"]


@admin.register(SportEvent)
class SportEventAdmin(admin.ModelAdmin):
    list_display = ["__str__", "sport", "league", "starts_at", "status"]
    list_filter = ["sport", "league", "status"]
    search_fields = ["home", "away"]
    inlines = [EventMarketInline]


@admin.register(EventMarket)
class EventMarketAdmin(admin.ModelAdmin):
    list_display = ["question", "event", "kind", "status", "resolution", "rule"]
    list_filter = ["kind", "status"]
    search_fields = ["question"]
    # Resolution must go through services (ledger); not editable here.
    readonly_fields = ["status", "resolution", "resolved_at"]


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ["name", "team", "position", "salary", "sport"]
    list_filter = ["team", "position", "sport"]
    search_fields = ["name", "team"]


@admin.register(FantasyContest)
class FantasyContestAdmin(admin.ModelAdmin):
    list_display = ["__str__", "salary_cap", "roster_size", "entry_fee"]
    filter_horizontal = ["player_pool"]


@admin.register(FantasyEntry)
class FantasyEntryAdmin(admin.ModelAdmin):
    list_display = ["contest", "user", "points", "rank", "payout"]
    readonly_fields = ["points", "rank", "payout"]


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ["market", "user", "side", "price", "quantity", "stake", "payout", "status"]
    list_filter = ["status", "side"]
    readonly_fields = ["stake", "payout", "status"]


@admin.register(PlayerStat)
class PlayerStatAdmin(admin.ModelAdmin):
    list_display = ["event", "player", "points"]


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "is_house", "balance", "locked"]
    # Balances only change through the double-entry ledger.
    readonly_fields = ["balance", "locked"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["transaction_id", "wallet", "amount", "kind", "ref", "created_at"]
    list_filter = ["kind"]
    search_fields = ["transaction_id", "ref"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
