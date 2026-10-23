from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "markets"

router = DefaultRouter()
router.register("events", views.SportEventViewSet, basename="event")
router.register("markets", views.EventMarketViewSet, basename="market")
router.register("positions", views.MyPositionViewSet, basename="position")
router.register("players", views.PlayerViewSet, basename="player")
router.register("fantasy/contests", views.FantasyContestViewSet, basename="fantasy-contest")
router.register("fantasy/entries", views.MyFantasyEntryViewSet, basename="fantasy-entry")
router.register("wallet/ledger", views.MyLedgerViewSet, basename="ledger")

urlpatterns = [
    path("wallet/", views.MyWalletView.as_view(), name="wallet"),
    path("", include(router.urls)),
]
