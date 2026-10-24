from rest_framework import serializers

from .models import Fixture, Gameweek, GameweekScore, League, Lineup, Player, PlayerGameStat, Season, Squad, Team, Transfer


class SeasonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Season
        fields = ["id", "liiga_season", "name", "is_current", "budget"]


class TeamSerializer(serializers.ModelSerializer):
    community = serializers.SlugRelatedField(slug_field="slug", read_only=True)

    class Meta:
        model = Team
        fields = ["id", "name", "abbreviation", "logo_url", "community"]


class GameweekSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gameweek
        fields = ["id", "number", "deadline", "status"]


class FixtureSerializer(serializers.ModelSerializer):
    home = TeamSerializer(read_only=True)
    away = TeamSerializer(read_only=True)
    gameweek = serializers.IntegerField(source="gameweek.number", read_only=True, default=None)

    class Meta:
        model = Fixture
        fields = ["id", "gameweek", "serie", "home", "away", "starts_at", "status", "home_goals", "away_goals",
                  "finished_type"]


class PlayerSerializer(serializers.ModelSerializer):
    team = serializers.CharField(source="team.name", read_only=True, default=None)
    team_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Player
        fields = ["id", "first_name", "last_name", "team", "team_id", "position", "jersey", "nationality",
                  "picture_url", "price", "total_points", "injured", "suspended", "active"]


class PlayerGameStatSerializer(serializers.ModelSerializer):
    fixture = FixtureSerializer(read_only=True)

    class Meta:
        model = PlayerGameStat
        fields = ["fixture", "points", "breakdown", "stats"]


class LineupSerializer(serializers.ModelSerializer):
    gameweek = serializers.IntegerField(source="gameweek.number", read_only=True)
    starters = serializers.SerializerMethodField()
    bench = serializers.SerializerMethodField()

    class Meta:
        model = Lineup
        fields = ["gameweek", "captain", "vice_captain", "starters", "bench"]

    def get_starters(self, obj):
        return [s.player_id for s in obj.slots.all() if s.is_starter]

    def get_bench(self, obj):
        return [s.player_id for s in obj.slots.all() if not s.is_starter]


class SquadSerializer(serializers.ModelSerializer):
    players = serializers.SerializerMethodField()
    first_gameweek = serializers.IntegerField(source="first_gameweek.number", read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = Squad
        fields = ["id", "name", "season", "bank", "value", "free_transfers", "first_gameweek", "total_points", "players"]

    def get_players(self, obj):
        picks = obj.picks.select_related("player__team")
        return [dict(PlayerSerializer(p.player).data, purchase_price=str(p.purchase_price)) for p in picks]

    def get_value(self, obj):
        return str(sum((p.player.price for p in obj.picks.select_related("player")), obj.bank))


class CreateSquadSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=60)
    player_ids = serializers.ListField(child=serializers.IntegerField())


class SetLineupSerializer(serializers.Serializer):
    starters = serializers.ListField(child=serializers.IntegerField())
    bench = serializers.ListField(child=serializers.IntegerField())
    captain = serializers.IntegerField()
    vice_captain = serializers.IntegerField()


class TransferRequestSerializer(serializers.Serializer):
    out = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    # `in` is a Python keyword, so the JSON field is mapped explicitly.
    in_ = serializers.ListField(child=serializers.IntegerField(), min_length=1)

    def to_internal_value(self, data):
        data = dict(data)
        if "in" in data:
            data["in_"] = data.pop("in")
        return super().to_internal_value(data)


class TransferSerializer(serializers.ModelSerializer):
    gameweek = serializers.IntegerField(source="gameweek.number", read_only=True)

    class Meta:
        model = Transfer
        fields = ["id", "gameweek", "player_out", "player_in", "price_out", "price_in", "point_cost", "created_at"]


class GameweekScoreSerializer(serializers.ModelSerializer):
    gameweek = serializers.IntegerField(source="gameweek.number", read_only=True)

    class Meta:
        model = GameweekScore
        fields = ["gameweek", "points", "transfer_cost", "total", "detail", "final"]


class LeagueSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="members.count", read_only=True)

    class Meta:
        model = League
        fields = ["id", "name", "code", "season", "member_count", "created_at"]
        read_only_fields = ["code", "season", "member_count", "created_at"]


class JoinLeagueSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)
