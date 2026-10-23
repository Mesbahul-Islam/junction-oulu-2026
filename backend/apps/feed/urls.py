from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ArrivalSequenceView, SnippetViewSet

router = DefaultRouter()
router.register("snippets", SnippetViewSet, basename="snippet")

urlpatterns = [
    path("arrival/", ArrivalSequenceView.as_view(), name="feed-arrival"),
    *router.urls,
]
