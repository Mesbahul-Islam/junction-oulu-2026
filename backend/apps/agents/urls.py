from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AgentRunViewSet, WebhookCompleteView

router = DefaultRouter()
router.register("runs", AgentRunViewSet, basename="agent-run")

urlpatterns = [
    path("webhook/complete/", WebhookCompleteView.as_view(), name="agent-webhook-complete"),
] + router.urls
