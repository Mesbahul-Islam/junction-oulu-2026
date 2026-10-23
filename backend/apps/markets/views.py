"""FR-5 markets API. All amounts are virtual points; there is no real-money flow."""

from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import has_role

from .models import EventMarket, FantasyContest, FantasyEntry, Player, Position, SportEvent
from .serializers import (
    EnterContestSerializer,
    EventMarketSerializer,
    FantasyContestSerializer,
    FantasyEntrySerializer,
    FinalScoreSerializer,
    LedgerEntrySerializer,
    PlaceOrderSerializer,
    PlayerSerializer,
    PositionSerializer,
    ResolveSerializer,
    SportEventSerializer,
    WalletSerializer,
)
from .services.ledger import MarketError, get_or_create_wallet
from .services.settlement import ingest_final_score, resolve_binary, void_market
from .services.trading import enter_fantasy_contest, place_binary_order


class ByStartTime(CursorPagination):
    ordering = "starts_at"


class IsMarketAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_staff or has_role(user, "admin")))


def _error(exc: Exception) -> Response:
    return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class SportEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SportEvent.objects.prefetch_related("markets")
    serializer_class = SportEventSerializer
    pagination_class = ByStartTime
    filterset_fields = ["sport", "league", "status"]

    @action(detail=True, methods=["post"], url_path="final-score", permission_classes=[IsMarketAdmin],
            serializer_class=FinalScoreSerializer)
    def final_score(self, request, pk=None):
        event = self.get_object()
        ser = FinalScoreSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            summary = ingest_final_score(event, ser.validated_data)
        except MarketError as exc:
            return _error(exc)
        event.refresh_from_db()
        return Response({"event": SportEventSerializer(event).data, "settlement": summary})


class EventMarketViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = EventMarket.objects.select_related("event", "contest")
    serializer_class = EventMarketSerializer
    filterset_fields = ["event", "kind", "status"]

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated],
            serializer_class=PlaceOrderSerializer)
    def order(self, request, pk=None):
        market = self.get_object()
        ser = PlaceOrderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            position = place_binary_order(request.user, market, **ser.validated_data)
        except MarketError as exc:
            return _error(exc)
        return Response(PositionSerializer(position).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsMarketAdmin], serializer_class=ResolveSerializer)
    def resolve(self, request, pk=None):
        market = self.get_object()
        ser = ResolveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        resolution = ser.validated_data["resolution"]
        try:
            market = void_market(market) if resolution == "void" else resolve_binary(market, resolution)
        except MarketError as exc:
            return _error(exc)
        return Response(EventMarketSerializer(market).data)


class MyPositionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PositionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["market", "status", "side"]

    def get_queryset(self):
        return Position.objects.filter(user=self.request.user).select_related("market")


class PlayerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer
    pagination_class = None
    filterset_fields = ["team", "sport", "position"]


class FantasyContestViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = FantasyContest.objects.select_related("market__event")
    serializer_class = FantasyContestSerializer
    filterset_fields = ["market__status"]

    @action(detail=True, methods=["get"])
    def players(self, request, pk=None):
        contest = self.get_object()
        qs = contest.player_pool.all()
        if not qs.exists():
            event = contest.market.event
            qs = Player.objects.filter(team__in=[event.home, event.away])
        return Response(PlayerSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"])
    def leaderboard(self, request, pk=None):
        contest = self.get_object()
        entries = contest.entries.select_related("user").prefetch_related("players").order_by("-points", "created_at")
        return Response(FantasyEntrySerializer(entries[:100], many=True).data)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated],
            serializer_class=EnterContestSerializer)
    def enter(self, request, pk=None):
        contest = self.get_object()
        ser = EnterContestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            entry = enter_fantasy_contest(request.user, contest, ser.validated_data["player_ids"])
        except MarketError as exc:
            return _error(exc)
        return Response(FantasyEntrySerializer(entry).data, status=status.HTTP_201_CREATED)


class MyFantasyEntryViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = FantasyEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FantasyEntry.objects.filter(user=self.request.user).prefetch_related("players")


class MyWalletView(APIView):
    """GET the caller's virtual-points wallet (created with the signup grant on first access)."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = WalletSerializer

    def get(self, request):
        return Response(WalletSerializer(get_or_create_wallet(request.user)).data)


class MyLedgerViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = LedgerEntrySerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["kind"]

    def get_queryset(self):
        wallet = get_or_create_wallet(self.request.user)
        return wallet.entries.all()
