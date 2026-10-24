from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

app_name = "fantasy"

router = DefaultRouter()
router.include_root_view = False  # views.FantasyRootView lists every endpoint instead
router.register("teams", views.TeamViewSet, basename="team")
router.register("fixtures", views.FixtureViewSet, basename="fixture")
router.register("players", views.PlayerViewSet, basename="player")
router.register("leagues", views.LeagueViewSet, basename="league")

urlpatterns = [
    path("", views.FantasyRootView.as_view(), name="root"),
    path("season/", views.CurrentSeasonView.as_view(), name="season"),
    path("squad/", views.SquadView.as_view(), name="squad"),
    path("squad/lineup/", views.LineupView.as_view(), name="lineup"),
    path("squad/transfers/", views.TransferView.as_view(), name="transfers"),
    path("squad/history/", views.HistoryView.as_view(), name="history"),
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
    path("", include(router.urls)),
]
