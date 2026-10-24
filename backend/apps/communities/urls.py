from rest_framework.routers import DefaultRouter

from . import views

app_name = "communities"

router = DefaultRouter()
router.register(r"groups/(?P<community_slug>[-\w]+)/posts", views.PostViewSet, basename="post")
router.register("groups", views.CommunityViewSet, basename="community")
router.register("news", views.CommunityNewsView, basename="community-news")
router.register("moderation", views.PostModerationViewSet, basename="post-moderation")
router.register("contributions", views.ContributionViewSet, basename="contribution")
router.register("feedback-prompts", views.FeedbackPromptViewSet, basename="feedback-prompt")
router.register("feedback-responses", views.FeedbackResponseViewSet, basename="feedback-response")
router.register("sources", views.SourceFeedViewSet, basename="source-feed")
router.register("glossary", views.GlossaryTermViewSet, basename="glossary-term")
router.register("context", views.ContextEntryViewSet, basename="context-entry")

urlpatterns = router.urls
