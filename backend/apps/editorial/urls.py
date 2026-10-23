from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import CorrectionViewSet, ReviewTaskViewSet, SnippetAuditView

router = DefaultRouter()
router.register("tasks", ReviewTaskViewSet, basename="review-task")
router.register("corrections", CorrectionViewSet, basename="correction")

urlpatterns = [
    path("snippets/<int:snippet_id>/audit/", SnippetAuditView.as_view(), name="snippet-audit"),
    *router.urls,
]
