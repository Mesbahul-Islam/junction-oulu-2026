"""Fantasy Liiga API (season-long, free to play)."""

from datetime import date

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from .auth import DevBypassAuthentication
from .models import Fixture, Gameweek, League, Player, Squad, Team
from .serializers import (
    CreateSquadSerializer,
    FixtureSerializer,
    GameweekScoreSerializer,
    GameweekSerializer,
    JoinLeagueSerializer,
    LeagueSerializer,
    LineupSerializer,
    PlayerGameStatSerializer,
    PlayerSerializer,
    SeasonSerializer,
    SetLineupSerializer,
    SquadSerializer,
    TeamSerializer,
    TransferRequestSerializer,
    TransferSerializer,
)
from .services import leaderboards
from .services.squads import (
    FantasyError,
    create_squad,
    current_season,
    lineup_for,
    make_transfers,
    next_open_gameweek,
    set_lineup,
)


# Real JWT / session auth first; in DEBUG, fall back to the dev bypass (see auth.py).
AUTHENTICATION = [*api_settings.DEFAULT_AUTHENTICATION_CLASSES, DevBypassAuthentication]


def _error(exc: Exception) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


def _my_squad(request) -> Squad:
    squad = Squad.objects.filter(user=request.user, season=current_season()).first()
    if squad is None:
        raise FantasyError("You don't have a squad yet: POST /api/fantasy/squad/ to create one")
    return squad


class FantasyRootView(APIView):
    """Every fantasy endpoint. The squad endpoints need a login (Authorize in /api/docs/)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        url = lambda name: reverse(f"fantasy:{name}", request=request)
        board = url("leaderboard")
        return Response({
            "season": url("season"),
            "leaderboard": board,
            "leaderboard_oulu": f"{board}?scope=community&community=oulu",
            "leaderboard_week": f"{board}?period=week&gameweek=<number>",
            "leaderboard_day": f"{board}?period=day&date=<YYYY-MM-DD>",
            "players": url("player-list"),
            "fixtures": url("fixture-list"),
            "teams": url("team-list"),
            "squad (login)": url("squad"),
            "lineup (login)": url("lineup"),
            "transfers (login)": url("transfers"),
            "history (login)": url("history"),
            "leagues (login)": url("league-list"),
        })


class CurrentSeasonView(APIView):
    """The current season, its gameweeks and the gameweek that changes apply to."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        try:
            season = current_season()
        except FantasyError as exc:
            return _error(exc)
        try:
            open_gw = next_open_gameweek(season).number
        except FantasyError:
            open_gw = None
        return Response({
            **SeasonSerializer(season).data,
            "next_deadline_gameweek": open_gw,
            "gameweeks": GameweekSerializer(season.gameweeks.all(), many=True).data,
        })


class TeamViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Team.objects.select_related("community")
    serializer_class = TeamSerializer
    pagination_class = None


class FixtureViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FixtureSerializer
    pagination_class = None
    filterset_fields = ["status"]

    def get_queryset(self):
        qs = Fixture.objects.filter(season__is_current=True).select_related("home", "away", "gameweek")
        if gw := self.request.query_params.get("gameweek"):
            qs = qs.filter(gameweek__number=gw)
        if team := self.request.query_params.get("team"):
            qs = qs.filter(Q(home_id=team) | Q(away_id=team))
        return qs


class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    """?position=G|D|F &team=<id> &search=<name> &ordering=price|-price|total_points|-total_points"""

    serializer_class = PlayerSerializer
    pagination_class = LimitOffsetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["position", "team", "injured", "active"]
    ordering_fields = ["price", "total_points", "last_name"]
    ordering = ["-total_points", "last_name"]
    search_fields = ["first_name", "last_name"]

    def get_queryset(self):
        return Player.objects.select_related("team").filter(team__isnull=False)

    @action(detail=True, methods=["get"])
    def games(self, request, pk=None):
        player = self.get_object()
        stats = player.game_stats.filter(fixture__season__is_current=True).select_related(
            "fixture__home", "fixture__away", "fixture__gameweek"
        ).order_by("-fixture__starts_at")
        return Response(PlayerGameStatSerializer(stats, many=True).data)


class SquadView(APIView):
    """GET your squad · POST {name, player_ids[15]} to create it."""

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = AUTHENTICATION
    serializer_class = CreateSquadSerializer

    def get(self, request):
        try:
            return Response(SquadSerializer(_my_squad(request)).data)
        except FantasyError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)

    def post(self, request):
        ser = CreateSquadSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            squad = create_squad(request.user, ser.validated_data["name"], ser.validated_data["player_ids"])
        except FantasyError as exc:
            return _error(exc)
        return Response(SquadSerializer(squad).data, status=status.HTTP_201_CREATED)


class LineupView(APIView):
    """GET ?gameweek=N (default: next deadline) · PUT {starters[11], bench[4], captain, vice_captain}."""

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = AUTHENTICATION
    serializer_class = SetLineupSerializer

    def get(self, request):
        try:
            squad = _my_squad(request)
            number = request.query_params.get("gameweek")
            gw = (get_object_or_404(Gameweek, season=squad.season, number=number) if number
                  else next_open_gameweek(squad.season))
        except FantasyError as exc:
            return _error(exc)
        lineup = lineup_for(squad, gw)
        data = LineupSerializer(lineup).data if lineup else {}
        return Response({**data, "gameweek": gw.number, "deadline": gw.deadline})

    def put(self, request):
        ser = SetLineupSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            lineup = set_lineup(_my_squad(request), d["starters"], d["bench"], d["captain"], d["vice_captain"])
        except FantasyError as exc:
            return _error(exc)
        return Response(LineupSerializer(lineup).data)


class TransferView(APIView):
    """GET your transfer history · POST {"out": [ids], "in": [ids]} for the next gameweek."""

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = AUTHENTICATION
    serializer_class = TransferRequestSerializer

    def get(self, request):
        try:
            squad = _my_squad(request)
        except FantasyError as exc:
            return _error(exc)
        return Response(TransferSerializer(squad.transfers.select_related("gameweek"), many=True).data)

    def post(self, request):
        ser = TransferRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            squad = _my_squad(request)
            transfers = make_transfers(squad, ser.validated_data["out"], ser.validated_data["in_"])
        except FantasyError as exc:
            return _error(exc)
        squad.refresh_from_db()
        return Response({
            "transfers": TransferSerializer(transfers, many=True).data,
            "squad": SquadSerializer(squad).data,
        }, status=status.HTTP_201_CREATED)


class HistoryView(APIView):
    """Your points per gameweek, with per-player detail."""

    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = AUTHENTICATION

    def get(self, request):
        try:
            squad = _my_squad(request)
        except FantasyError as exc:
            return _error(exc)
        scores = squad.gameweek_scores.select_related("gameweek").order_by("gameweek__number")
        return Response(GameweekScoreSerializer(scores, many=True).data)


class LeaderboardView(APIView):
    """?period=day|week|season &scope=global|community|league
    &date=YYYY-MM-DD (day) &gameweek=N (week) &community=<slug> &league=<id>"""

    permission_classes = [permissions.AllowAny]
    authentication_classes = AUTHENTICATION

    def get(self, request):
        p = request.query_params
        try:
            season = current_season()
            gameweek = get_object_or_404(Gameweek, season=season, number=p["gameweek"]) if p.get("gameweek") else None
            league = get_object_or_404(League, pk=p["league"], season=season) if p.get("league") else None
            day = date.fromisoformat(p["date"]) if p.get("date") else None
            board = leaderboards.leaderboard(
                season, p.get("period", "season"), p.get("scope", "global"), day=day, gameweek=gameweek,
                community=p.get("community"), league=league, limit=min(int(p.get("limit", 100)), 500),
                user=request.user,
            )
        except (FantasyError, ValueError) as exc:
            return _error(exc)
        return Response(board)


class LeagueViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    """Private leagues you're in. POST {name} to create one; POST join/ {code} to join a friend's."""

    serializer_class = LeagueSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = AUTHENTICATION
    pagination_class = None

    def get_queryset(self):
        return League.objects.filter(members__user=self.request.user, season__is_current=True)

    def create(self, request, *args, **kwargs):
        ser = LeagueSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            league = leaderboards.create_league(_my_squad(request), ser.validated_data["name"])
        except FantasyError as exc:
            return _error(exc)
        return Response(LeagueSerializer(league).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], serializer_class=JoinLeagueSerializer)
    def join(self, request):
        ser = JoinLeagueSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            league = leaderboards.join_league(_my_squad(request), ser.validated_data["code"])
        except FantasyError as exc:
            return _error(exc)
        return Response(LeagueSerializer(league).data)
