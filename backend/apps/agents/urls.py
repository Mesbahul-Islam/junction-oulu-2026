from rest_framework.routers import DefaultRouter

from django.urls import path

from .views import AgentRunViewSet, DashboardView

router = DefaultRouter()
router.register("runs", AgentRunViewSet, basename="agent-run")

urlpatterns = [path("dashboard/", DashboardView.as_view(), name="agents-dashboard")] + router.urls
