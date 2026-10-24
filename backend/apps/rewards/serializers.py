from rest_framework import serializers

from .models import ContributorStats, Level, Perk, Plan, Redemption
from .services import next_step


# --- Incoming statistics (POST /api/rewards/stats/) ---

class ContributionsIn(serializers.Serializer):
    posts_approved = serializers.IntegerField(min_value=0, default=0)
    photos_approved = serializers.IntegerField(min_value=0, default=0)
    corrections_accepted = serializers.IntegerField(min_value=0, default=0)
    rejected = serializers.IntegerField(min_value=0, default=0)


class RatingIn(serializers.Serializer):
    average = serializers.DecimalField(max_digits=3, decimal_places=2, min_value=0, max_value=5, default=0)
    count = serializers.IntegerField(min_value=0, default=0)


class MemberStatsIn(serializers.Serializer):
    """One member. Identify them by user_id, email or username."""

    user_id = serializers.IntegerField(required=False)
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False, max_length=150)
    period = serializers.CharField(required=False, max_length=20, default="")
    contributions = ContributionsIn(required=False, default=dict)
    community_rating = RatingIn(required=False, default=dict)
    trusted_voice = serializers.BooleanField(required=False, default=False)
    trust_score = serializers.IntegerField(required=False, default=0)

    def validate(self, data):
        if not (data.get("user_id") or data.get("email") or data.get("username")):
            raise serializers.ValidationError("Give user_id, email or username.")
        return data


class IngestSerializer(serializers.Serializer):
    source = serializers.CharField(required=False, max_length=60, default="")
    members = MemberStatsIn(many=True, allow_empty=False)


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


class StatsSerializer(serializers.ModelSerializer):
    level_label = serializers.SerializerMethodField()
    next = serializers.SerializerMethodField()

    class Meta:
        model = ContributorStats
        fields = ["points", "level", "level_label", "next", "period", "posts_approved", "photos_approved",
                  "corrections_accepted", "rejected", "rating_average", "rating_count", "trusted_voice", "updated_at"]

    def get_level_label(self, stats):
        return Level(stats.level).label

    def get_next(self, stats):
        return next_step(stats)
