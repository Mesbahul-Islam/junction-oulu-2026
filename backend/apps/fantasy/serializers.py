from django.urls import reverse
from rest_framework import serializers

from .services.photos import PHOTO_VERSION
from .models import PlayerNote, Reward, Sponsor, Voucher
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
    # Small cached thumbnail for the app (picture_url is Liiga's ~450 KB original).
    photo_url = serializers.SerializerMethodField()
    # Points it costs to bring him into your team after your first deadline (by his rank).
    transfer_cost = serializers.SerializerMethodField()

    def get_transfer_cost(self, obj):
        from .services.squads import transfer_costs

        return transfer_costs().get(obj.pk)

    class Meta:
        model = Player
        fields = ["id", "first_name", "last_name", "team", "team_id", "position", "jersey", "nationality",
                  "picture_url", "photo_url", "price", "total_points", "injured", "suspended", "active", "transfer_cost"]

    def get_photo_url(self, obj):
        if not obj.picture_url:
            return None
        url = f'{reverse("fantasy:player-photo", args=[obj.pk])}?v={PHOTO_VERSION}'
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url


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
    manager = serializers.CharField(source="user.username", read_only=True)
    standing = serializers.SerializerMethodField()
    free_changes = serializers.SerializerMethodField()
    points_spent = serializers.SerializerMethodField()

    def get_free_changes(self, obj):
        from .services.squads import changes_are_free

        return changes_are_free(obj)

    def get_points_spent(self, obj):
        """Points spent on changes for the next gameweek so far."""
        from django.db.models import Sum

        from .services.squads import next_open_gameweek

        try:
            gw = next_open_gameweek(obj.season)
        except Exception:
            return 0
        return obj.transfers.filter(gameweek=gw).aggregate(s=Sum("point_cost"))["s"] or 0
    players = serializers.SerializerMethodField()
    first_gameweek = serializers.IntegerField(source="first_gameweek.number", read_only=True)
    value = serializers.SerializerMethodField()

    class Meta:
        model = Squad
        fields = ["id", "name", "manager", "season", "bank", "value", "free_transfers", "first_gameweek", "total_points",
                  "standing", "free_changes", "points_spent", "players"]

    def get_standing(self, obj):
        from .services.leaderboards import season_standing

        return season_standing(obj)

    def get_players(self, obj):
        picks = obj.picks.select_related("player__team")
        return [dict(PlayerSerializer(p.player, context=self.context).data, purchase_price=str(p.purchase_price)) for p in picks]

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
    player_out_name = serializers.CharField(source="player_out.name", read_only=True)
    player_in_name = serializers.CharField(source="player_in.name", read_only=True)

    class Meta:
        model = Transfer
        fields = ["id", "gameweek", "player_out", "player_in", "player_out_name", "player_in_name", "price_out", "price_in",
                  "point_cost", "created_at"]


class GameweekScoreSerializer(serializers.ModelSerializer):
    gameweek = serializers.IntegerField(source="gameweek.number", read_only=True)

    class Meta:
        model = GameweekScore
        fields = ["gameweek", "points", "transfer_cost", "total", "detail", "final"]


class LeagueSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="members.count", read_only=True)
    owner = serializers.CharField(source="owner.username", read_only=True)
    members = serializers.SerializerMethodField()

    class Meta:
        model = League
        fields = ["id", "name", "code", "season", "owner", "member_count", "members", "created_at"]
        read_only_fields = ["code", "season", "owner", "member_count", "members", "created_at"]

    def get_members(self, obj):
        squads = obj.members.select_related("user").order_by("-total_points", "created_at")
        return [{"username": s.user.username, "squad_id": s.pk, "squad_name": s.name, "total_points": float(s.total_points)}
                for s in squads]


class JoinLeagueSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)


class InviteSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=31)


def media_url(request, path: str) -> str:
    from django.conf import settings

    url = "/" + settings.MEDIA_URL.strip("/") + "/" + path
    return request.build_absolute_uri(url) if request else url


class SponsorSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Sponsor
        fields = ["slug", "name", "tagline", "website", "logo_url"]

    def get_logo_url(self, obj):
        return media_url(self.context.get("request"), obj.logo) if obj.logo else None


def _lang(serializer) -> str:
    request = serializer.context.get("request")
    return "fi" if request and getattr(request.user, "preferred_language", "") == "fi" else "en"


class RewardSerializer(serializers.ModelSerializer):
    sponsor = SponsorSerializer(read_only=True)
    player = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    def get_title(self, obj):
        return obj.title_fi if _lang(self) == "fi" and obj.title_fi else obj.title

    def get_description(self, obj):
        return obj.description_fi if _lang(self) == "fi" and obj.description_fi else obj.description

    class Meta:
        model = Reward
        fields = ["id", "sponsor", "kind", "title", "description", "period", "scope", "community_slug", "rank_from", "rank_to",
                  "threshold", "tier", "player"]

    def get_player(self, obj):
        return PlayerSerializer(obj.player, context=self.context).data if obj.player else None


class VoucherSerializer(serializers.ModelSerializer):
    reward = RewardSerializer(read_only=True)
    gameweek = serializers.IntegerField(source="gameweek.number", read_only=True, default=None)

    class Meta:
        model = Voucher
        fields = ["id", "reward", "gameweek", "rank", "code", "expires_at", "redeemed_at", "created_at"]


class PlayerNoteSerializer(serializers.ModelSerializer):
    player = PlayerSerializer(read_only=True)
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()

    def _text(self, obj):
        """Form and status notes are written in the reader's language from their facts. Kaleva stories stay as published."""
        lang = _lang(self)
        if obj.kind == PlayerNote.Kind.FORM and obj.facts:
            from .services.sports_desk import form_text

            if lang == "en" and obj.wording == "ai":
                return obj.title, obj.body
            title, lines = form_text(obj.facts, lang)
            return title, " ".join(lines)
        if obj.kind == PlayerNote.Kind.STATUS and "suspended" in obj.facts:
            sus = obj.facts["suspended"]
            return (("Pelikiellossa" if sus else "Taas pelikunnossa") if lang == "fi" else ("Suspended" if sus else "Available again")), ""
        return obj.title, obj.body

    def get_title(self, obj):
        return self._text(obj)[0]

    def get_body(self, obj):
        return self._text(obj)[1]
    # The same story in our own app, once the newsroom has published it (else null).
    story_id = serializers.SerializerMethodField()

    class Meta:
        model = PlayerNote
        fields = ["id", "player", "kind", "title", "body", "url", "source", "wording", "published_at", "story_id"]

    def get_story_id(self, obj):
        if not obj.url:
            return None
        from apps.feed.models import Snippet

        return (Snippet.objects.filter(source_documents__url=obj.url, review_status="published")
                .order_by("-published_at").values_list("pk", flat=True).first())
