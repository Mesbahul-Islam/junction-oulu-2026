from django.contrib import admin

from .models import Partner, Perk, Plan, Redemption


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
