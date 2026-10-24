from django.contrib import admin

from .models import ContributorStats, Partner, Perk, Plan, Redemption


@admin.register(ContributorStats)
class ContributorStatsAdmin(admin.ModelAdmin):
    list_display = ["user", "level", "points", "posts_approved", "photos_approved", "corrections_accepted",
                    "rating_average", "trusted_voice", "updated_at"]
    list_filter = ["level", "trusted_voice"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["points", "level", "payload"]


class PerkInline(admin.StackedInline):
    model = Perk
    extra = 0


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "city"]
    prepopulated_fields = {"slug": ["name"]}
    inlines = [PerkInline]


@admin.register(Perk)
class PerkAdmin(admin.ModelAdmin):
    list_display = ["partner", "title", "off_contributor", "off_local_guide", "off_trusted", "stock", "active"]
    list_filter = ["active"]


@admin.register(Redemption)
class RedemptionAdmin(admin.ModelAdmin):
    list_display = ["code", "user", "perk", "month", "valid_until", "used_at"]
    search_fields = ["code", "user__email"]
    list_filter = ["month"]


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["user", "billing", "renews_on", "cancelled_at"]
    list_filter = ["billing"]
