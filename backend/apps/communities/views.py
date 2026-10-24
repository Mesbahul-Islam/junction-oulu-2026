"""Communities API. FR-1.2 communities/posts, FR-3.10 feedback, FR-3.12 contributions, FR-3.14 config."""

from django.db.models import Count
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from . import services
from .models import (
    CommunityContribution,
    CommunityGroup,
    ContextEntry,
    FeedbackPrompt,
    FeedbackResponse,
    GlossaryTerm,
    Post,
    SourceFeed,
)
from .permissions import IsAuthorOrReadOnly, IsCommunityAdmin, IsCommunityMember
from .serializers import (
    CommunityContributionSerializer,
    CommunityGroupSerializer,
    ContextEntrySerializer,
    FeedbackPromptSerializer,
    FeedbackResponseSerializer,
    GlossaryTermSerializer,
    FlagPostSerializer,
    ModeratePostSerializer,
    ModerationPostSerializer,
    PostSerializer,
    SourceFeedSerializer,
)


class CreatedAtCursorPagination(CursorPagination):
    """Project default CursorPagination orders by '-created' which doesn't exist on TimeStampedModel."""

    ordering = "-created_at"


class CommunityViewSet(viewsets.ReadOnlyModelViewSet):
    """FR-1.2: list/detail communities, join/leave. Lookup by slug."""

    serializer_class = CommunityGroupSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    lookup_field = "slug"
    pagination_class = None  # small set; return all
    filterset_fields = ["kind", "municipality"]

    def get_queryset(self):
        return CommunityGroup.objects.filter(is_active=True).annotate(member_count=Count("memberships"))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def join(self, request, slug=None):
        membership = services.join_community(request.user, self.get_object())
        return Response({"community": slug, "role": membership.role}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def leave(self, request, slug=None):
        services.leave_community(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostViewSet(viewsets.ModelViewSet):
    """FR-1.2: /communities/<slug>/posts/ — threaded posts, members only (queryset + permission).

    `?parent=<id>` lists replies; default lists top-level posts.
    """

    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated, IsCommunityMember, IsAuthorOrReadOnly]

    @cached_property
    def community(self):
        return get_object_or_404(CommunityGroup, slug=self.kwargs["community_slug"], is_active=True)

    def get_queryset(self):
        qs = (
            Post.objects.filter(community=self.community, community__memberships__user=self.request.user)
            .exclude(status=Post.Status.REMOVED)
            .select_related("author")
        )
        if not services.can_moderate(self.request.user, self.community):
            # Flagged posts stay hidden until moderated; their author still sees them (with a notice).
            qs = qs.filter(status=Post.Status.VISIBLE) | qs.filter(author=self.request.user)
        if self.action == "list":
            parent = self.request.query_params.get("parent")
            qs = qs.filter(parent_id=parent) if parent else qs.filter(parent__isnull=True)
        return qs

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "community": self.community}

    def perform_create(self, serializer):
        # Announcements carry the community's authority: only its moderators may post them.
        kind = serializer.validated_data.get("kind", Post.Kind.POST)
        if kind in (Post.Kind.ANNOUNCEMENT, Post.Kind.SNIPPET) and not services.can_moderate(self.request.user, self.community):
            kind = Post.Kind.POST
        serializer.save(community=self.community, author=self.request.user, kind=kind)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCommunityMember])
    def flag(self, request, community_slug=None, pk=None):
        """JSN annex L3: any member can flag a post; it's hidden until a moderator reviews it."""
        ser = FlagPostSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.flag_post(self.get_object(), request.user, **ser.validated_data)
        return Response({"detail": "Thanks. The post is hidden until a moderator reviews it."})


class CommunityNewsView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/communities/news/: posts by members of all the reader's communities, newest first.

    Reader-written content, not journalism: the app labels it as not reviewed by editors.
    """

    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        ids = self.request.user.memberships.values_list("community_id", flat=True)
        return services.visible_posts(self.request.user, ids)


class PostModerationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/communities/moderation/: flagged posts in communities you moderate (JSN annex L2, L4).
    POST /api/communities/moderation/<id>/decide/ {"decision": "keep"|"remove", "note"}."""

    serializer_class = ModerationPostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """?status=pending (default, reported and hidden) | removed | kept (reported, then restored)."""
        view = self.request.query_params.get("status", "pending")
        qs = Post.objects.select_related("author", "community", "moderated_by").prefetch_related("flags__user")
        if view == "removed":
            qs = qs.filter(status=Post.Status.REMOVED)
        elif view == "kept":
            qs = qs.filter(status=Post.Status.VISIBLE, moderated_at__isnull=False)
        else:
            qs = qs.filter(status=Post.Status.HIDDEN)
        ids = [p.pk for p in qs if services.can_moderate(self.request.user, p.community)]
        return qs.filter(pk__in=ids).order_by("-moderated_at", "-created_at")

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        post = get_object_or_404(Post, pk=pk)
        if not services.can_moderate(request.user, post.community):
            return Response({"detail": "Only moderators of this community can decide."}, status=status.HTTP_403_FORBIDDEN)
        ser = ModeratePostSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        post = services.moderate_post(post, request.user, ser.validated_data["decision"], ser.validated_data.get("note", ""))
        return Response(ModerationPostSerializer(post, context={"request": request}).data)


class ContributionViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                          viewsets.GenericViewSet):
    """FR-3.10/3.12: submit a question/tip/topic/bridge story; list own submissions.

    Contributions are never auto-published; editors triage them in admin/editorial.
    """

    serializer_class = CommunityContributionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["community", "kind", "status"]

    def get_queryset(self):
        return CommunityContribution.objects.filter(author=self.request.user)

    def create(self, request, *args, **kwargs):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        contribution, created = services.submit_contribution(author=request.user, **ser.validated_data)
        return Response(
            self.get_serializer(contribution).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class FeedbackPromptViewSet(viewsets.ReadOnlyModelViewSet):
    """FR-3.10: active 'what was useful / missing' prompts. Filter by ?community=&language=."""

    serializer_class = FeedbackPromptSerializer
    permission_classes = [permissions.AllowAny]
    queryset = FeedbackPrompt.objects.filter(is_active=True)
    pagination_class = None
    filterset_fields = ["community", "language"]


class FeedbackResponseViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """FR-3.10: submit a response to a prompt; list own responses."""

    serializer_class = FeedbackResponseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return FeedbackResponse.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class _AdminConfigViewSet(viewsets.ModelViewSet):
    """FR-3.14: admin-only CRUD so sources/glossary/context are configurable without code changes."""

    permission_classes = [IsCommunityAdmin]


class SourceFeedViewSet(_AdminConfigViewSet):
    serializer_class = SourceFeedSerializer
    queryset = SourceFeed.objects.select_related("community")
    filterset_fields = ["community", "kind", "is_active"]


class GlossaryTermViewSet(_AdminConfigViewSet):
    serializer_class = GlossaryTermSerializer
    queryset = GlossaryTerm.objects.all()
    filterset_fields = ["community", "language"]


class ContextEntryViewSet(_AdminConfigViewSet):
    """FR-3.8 context library. Admin edits count as human review (sets reviewed_by/at)."""

    serializer_class = ContextEntrySerializer
    queryset = ContextEntry.objects.all()
    filterset_fields = ["community", "language"]

    def _save_reviewed(self, serializer):
        serializer.save(reviewed_by=self.request.user, reviewed_at=timezone.now())

    perform_create = _save_reviewed
    perform_update = _save_reviewed
