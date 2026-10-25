"""Communities API. FR-1.2 communities/posts, FR-3.10 feedback, FR-3.12 contributions, FR-3.14 config."""

from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.functional import cached_property
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from . import photos, services
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
    RecommendedCommunitySerializer,
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
        return CommunityGroup.objects.filter(is_active=True).annotate(member_count=Count("memberships")).prefetch_related("interests")

    @action(detail=False, permission_classes=[permissions.IsAuthenticated])
    def recommended(self, request):
        """Communities to join, ranked against the reader's profile, each with its reasons."""
        items = []
        for group, score, reasons in services.recommend_communities(request.user):
            group.score, group.reasons = round(score, 2), reasons
            items.append(group)
        return Response(RecommendedCommunitySerializer(items, many=True, context={"request": request}).data)

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
            # Replies read top to bottom, oldest first; posts newest first.
            qs = qs.filter(parent_id=parent).order_by("created_at") if parent else qs.filter(parent__isnull=True)
            qs = services.with_engagement(qs.prefetch_related("translations"), self.request.user)
        return qs

    def paginate_queryset(self, queryset):
        if self.request.query_params.get("parent"):
            return None  # a reply thread comes whole, oldest first
        return super().paginate_queryset(queryset)

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "community": self.community}

    def perform_create(self, serializer):
        # Announcements carry the community's authority: only its moderators may post them.
        kind = serializer.validated_data.get("kind", Post.Kind.POST)
        if kind in (Post.Kind.ANNOUNCEMENT, Post.Kind.SNIPPET) and not services.can_moderate(self.request.user, self.community):
            kind = Post.Kind.POST
        extra = {}
        upload = serializer.validated_data.pop("image", None)
        if upload:
            # Faces are blurred now, before anything is stored (photos.py); a moderator checks it next.
            from .photos import PhotoError, blur_faces

            try:
                result = blur_faces(upload)
            except PhotoError as exc:
                raise ValidationError({"image": [str(exc)]}) from exc
            extra = {"image": result["file"], "image_status": "pending", "faces_blurred": result["faces"],
                     "image_notes": result["notes"]}
        post = serializer.save(community=self.community, author=self.request.user, kind=kind, **extra)
        services.register_post(post)

    @action(detail=True, methods=["post", "delete"], permission_classes=[permissions.IsAuthenticated, IsCommunityMember])
    def like(self, request, community_slug=None, pk=None):
        """POST likes the post (or reply), DELETE takes the like back."""
        count = services.set_like(self.get_object(), request.user, liked=request.method == "POST")
        return Response({"liked": request.method == "POST", "like_count": count})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCommunityMember])
    def share(self, request, community_slug=None, pk=None):
        """Count a share (the app opens the phone's share sheet or copies the text)."""
        return Response({"share_count": services.record_share(self.get_object())})

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsCommunityMember])
    def flag(self, request, community_slug=None, pk=None):
        """JSN annex L3: any member can flag a post; it's hidden until a moderator reviews it."""
        ser = FlagPostSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.flag_post(self.get_object(), request.user, **ser.validated_data)
        if ser.validated_data.get("reason") in services.CONTEXT_REASONS:
            return Response({"detail": "Thanks. Members will be asked to add a note with context.", "hidden": False})
        return Response({"detail": "Thanks. The post is hidden until a moderator reviews it.", "hidden": True})


class CommunityNewsView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/communities/news/: posts by members of all the reader's communities, newest first.

    Reader-written content, not journalism: the app labels it as not reviewed by editors.
    """

    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        ids = self.request.user.memberships.values_list("community_id", flat=True)
        qs = (services.visible_posts(self.request.user, ids).select_related("question__linked_snippet")
              .prefetch_related("translations", "flags", "community_notes__ratings"))
        return services.with_engagement(qs, self.request.user)

    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        """POST /api/communities/news/<id>/answer/ {"snippet": <id>}: an editor or community editor
        links the newsroom story that answers this question post."""
        from apps.feed.models import Snippet

        post = get_object_or_404(Post, pk=pk)
        if not services.can_moderate(request.user, post.community):
            return Response({"detail": "Only editors of this community can link answers."}, status=status.HTTP_403_FORBIDDEN)
        snippet = get_object_or_404(Snippet, pk=request.data.get("snippet"))
        services.answer_post(post, snippet, request.user)
        return Response(PostSerializer(post, context=self.get_serializer_context()).data)


class PostModerationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/communities/moderation/: flagged posts in communities you moderate (JSN annex L2, L4).
    POST /api/communities/moderation/<id>/decide/ {"decision": "keep"|"remove", "note"}."""

    serializer_class = ModerationPostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """?status=pending (default, reported and hidden) | removed | kept (reported, then restored)
        | questions (question posts the newsroom hasn't answered yet)."""
        view = self.request.query_params.get("status", "pending")
        qs = Post.objects.select_related("author", "community", "moderated_by").prefetch_related("flags__user")
        if view == "questions":
            qs = qs.filter(status=Post.Status.VISIBLE, parent__isnull=True, question__isnull=False,
                           question__linked_snippet__isnull=True)
        elif view == "removed":
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


class PhotoReviewViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/communities/photos/: photos waiting for a moderator, in communities you moderate.
    POST /api/communities/photos/<id>/decide/ {"decision": "approve"|"reject", "note": ""}.
    Faces were already blurred on upload; the moderator checks the blurring worked."""

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def list(self, request):
        qs = (Post.objects.filter(image_status="pending").exclude(status=Post.Status.REMOVED)
              .select_related("author", "community").order_by("created_at"))
        rows = [p for p in qs if services.can_moderate(request.user, p.community)]
        return Response([{
            "id": p.pk, "author_name": p.author.username, "community_name": p.community.name, "body": p.body,
            "image": photos.signed_url(request, p), "faces_blurred": p.faces_blurred,
            "notes": p.image_notes, "created_at": p.created_at,
        } for p in rows])

    @action(detail=True, methods=["post"])
    def decide(self, request, pk=None):
        post = get_object_or_404(Post.objects.select_related("community"), pk=pk, image_status="pending")
        if not services.can_moderate(request.user, post.community):
            return Response({"detail": "Only moderators of this community can decide."}, status=status.HTTP_403_FORBIDDEN)
        decision = request.data.get("decision")
        if decision not in ("approve", "reject"):
            return Response({"detail": "decision must be approve or reject"}, status=status.HTTP_400_BAD_REQUEST)
        post.image_checked_by, post.image_checked_at = request.user, timezone.now()
        post.image_status = "approved" if decision == "approve" else "rejected"
        if decision == "reject":
            post.image.delete(save=False)  # the photo is gone; the text stays
            post.image = None
        post.save(update_fields=["image", "image_status", "image_checked_by", "image_checked_at", "updated_at"])
        return Response({"id": post.pk, "image_status": post.image_status})


def post_photo(request, token):
    """GET /api/communities/photo/<signed token>/: a post's photo. The token is the permission: the
    API signs it only for people allowed to see the photo, and it expires (photos.LINK_MAX_AGE)."""
    post_id = photos.post_id_from(token)
    post = Post.objects.filter(pk=post_id).exclude(status=Post.Status.REMOVED).exclude(image="").first() if post_id else None
    if not post or not post.image:
        raise Http404
    response = FileResponse(post.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response
