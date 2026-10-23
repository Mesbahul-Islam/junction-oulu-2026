from rest_framework.routers import DefaultRouter

from .views import CommunityNoteViewSet

router = DefaultRouter()
router.register("notes", CommunityNoteViewSet, basename="community-note")

urlpatterns = router.urls
