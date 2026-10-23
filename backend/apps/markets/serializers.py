from decimal import Decimal

from django.db.models import Sum
from rest_framework import serializers

from .models import (
    MIN_PRICE,
    ONE,
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


class PlayerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Player
        fields = ["id", "name", "team", "sport", "salary", "position"]


class EventMarketSerializer(serializers.ModelSerializer):
    event_label = serializers.CharField(source="event.__str__", read_only=True)
    yes_price = serializers.SerializerMethodField()
    volume = serializers.SerializerMethodField()
    contest_id = serializers.SerializerMethodField()

    class Meta:
        model = EventMarket
        fields = [
            "id", "event", "event_label", "kind", "question", "status", "resolution",
            "rule", "line", "resolved_at", "yes_price", "volume", "contest_id", "created_at",
        ]
        read_only_fields = fields

    def get_yes_price(self, obj):
        """Implied YES probability: quantity-weighted average of YES prices and (1 - NO prices)."""
        if obj.kind != EventMarket.Kind.BINARY:
            return None
        total_qty, weighted = 0, Decimal("0")
        for side, price, qty in obj.positions.values_list("side", "price", "quantity"):
            weighted += (price if side == Position.Side.YES else ONE - price) * qty
            total_qty += qty
        if not total_qty:
            return "0.50"
        return str((weighted / total_qty).quantize(Decimal("0.01")))

    def get_volume(self, obj):
        return str(obj.positions.aggregate(s=Sum("stake"))["s"] or Decimal("0.00"))

    def get_contest_id(self, obj):
        contest = getattr(obj, "contest", None) if obj.kind == EventMarket.Kind.FANTASY else None
        return contest.pk if contest else None


class SportEventSerializer(serializers.ModelSerializer):
    markets = EventMarketSerializer(many=True, read_only=True)

    class Meta:
        model = SportEvent
        fields = ["id", "sport", "league", "home", "away", "starts_at", "status", "final_score", "markets"]


class PlaceOrderSerializer(serializers.Serializer):
    side = serializers.ChoiceField(choices=Position.Side.choices)
    price = serializers.DecimalField(max_digits=3, decimal_places=2, min_value=MIN_PRICE, max_value=ONE)
    quantity = serializers.IntegerField(min_value=1, max_value=100000)


class PositionSerializer(serializers.ModelSerializer):
    question = serializers.CharField(source="market.question", read_only=True)
    market_status = serializers.CharField(source="market.status", read_only=True)

    class Meta:
        model = Position
        fields = [
            "id", "market", "question", "market_status", "side", "price", "quantity",
            "stake", "payout", "status", "created_at",
        ]
        read_only_fields = fields


class FantasyContestSerializer(serializers.ModelSerializer):
    event = SportEventSerializer(source="market.event", read_only=True)
    status = serializers.CharField(source="market.status", read_only=True)
    question = serializers.CharField(source="market.question", read_only=True)
    entries_count = serializers.IntegerField(source="entries.count", read_only=True)
    prize_pool = serializers.SerializerMethodField()

    class Meta:
        model = FantasyContest
        fields = [
            "id", "market", "question", "status", "event", "salary_cap", "roster_size",
            "entry_fee", "prize_structure", "entries_count", "prize_pool",
        ]

    def get_prize_pool(self, obj):
        return str((obj.entry_fee * obj.entries.count()).quantize(Decimal("0.01")))


class EnterContestSerializer(serializers.Serializer):
    player_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)


class FantasyEntrySerializer(serializers.ModelSerializer):
    players = PlayerSerializer(many=True, read_only=True)
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = FantasyEntry
        fields = ["id", "contest", "user_display", "players", "points", "rank", "payout", "created_at"]
        read_only_fields = fields

    def get_user_display(self, obj):
        return getattr(obj.user, "display_name", "") or f"user-{obj.user_id}"


class PlayerStatSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)

    class Meta:
        model = PlayerStat
        fields = ["id", "event", "player", "stats", "points"]


class WalletSerializer(serializers.ModelSerializer):
    currency = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ["id", "balance", "locked", "currency", "updated_at"]
        read_only_fields = fields

    def get_currency(self, obj):
        return "virtual_points"


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "transaction_id", "amount", "kind", "ref", "memo", "created_at"]
        read_only_fields = fields


class ResolveSerializer(serializers.Serializer):
    resolution = serializers.ChoiceField(choices=[("yes", "Yes"), ("no", "No"), ("void", "Void")])


class FinalScoreSerializer(serializers.Serializer):
    home_score = serializers.IntegerField(min_value=0)
    away_score = serializers.IntegerField(min_value=0)
    player_stats = serializers.JSONField(required=False, default=dict)
    source = serializers.CharField(required=False, default="manual", max_length=64)
