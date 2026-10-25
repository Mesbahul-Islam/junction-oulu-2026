from rest_framework import serializers

from .models import Level, Perk, Plan, Redemption


# --- What the member sees ---

LADDER = [Level.CONTRIBUTOR, Level.LOCAL_GUIDE, Level.TRUSTED]


class PerkSerializer(serializers.ModelSerializer):
    """One partner's offer as the member sees it: the % off at their level and at every level."""

    partner = serializers.CharField(source="partner.name")
    slug = serializers.CharField(source="partner.slug")
    category = serializers.CharField(source="partner.category")
    city = serializers.CharField(source="partner.city")
    ladder = serializers.SerializerMethodField()
    percent = serializers.SerializerMethodField()
    min_level = serializers.SerializerMethodField()
    min_level_label = serializers.SerializerMethodField()
    sold_out = serializers.SerializerMethodField()

    class Meta:
        model = Perk
        fields = ["id", "partner", "slug", "category", "city", "title", "terms", "ladder", "percent", "min_level",
                  "min_level_label", "code_valid_days", "sold_out"]

    def get_ladder(self, perk):
        return [{"level": lvl, "label": Level(lvl).label, "percent": perk.percent_for(lvl)} for lvl in LADDER]

    def get_percent(self, perk):
        return perk.percent_for(self.context["level"])

    def get_min_level(self, perk):
        return perk.min_level

    def get_min_level_label(self, perk):
        return Level(perk.min_level).label if perk.min_level else None

    def get_sold_out(self, perk):
        return perk.stock == 0


class RedemptionSerializer(serializers.ModelSerializer):
    partner = serializers.CharField(source="perk.partner.name")
    slug = serializers.CharField(source="perk.partner.slug")
    title = serializers.CharField(source="perk.title")
    terms = serializers.CharField(source="perk.terms")

    class Meta:
        model = Redemption
        fields = ["id", "perk", "partner", "slug", "title", "terms", "percent", "code", "month", "valid_until", "used_at",
                  "created_at"]


class PlanSerializer(serializers.ModelSerializer):
    price = serializers.CharField(source="get_billing_display")

    class Meta:
        model = Plan
        fields = ["billing", "price", "renews_on", "cancelled_at"]
