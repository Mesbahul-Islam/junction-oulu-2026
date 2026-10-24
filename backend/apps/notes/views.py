"""Community Notes API (FR-4)."""

from rest_framework import exceptions, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import CommunityNote
from .serializers import CommunityNoteSerializer, NoteRatingSerializer, PublicNoteSerializer


class CommunityNoteViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """GET/POST /api/notes/notes/ (?snippet=, ?post=, ?status=) — all notes, for raters.
    POST /api/notes/notes/{id}/rate/ {value, tags[]} — upsert rating, recomputes status.
    GET /api/notes/notes/public/ (?snippet=, ?post=) — helpful notes only."""

    serializer_class = CommunityNoteSerializer
    filterset_fields = ["snippet", "post", "status"]

    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        from django.db.models import Q

        qs = CommunityNote.objects.prefetch_related("ratings").order_by("-created_at")
        user = self.request.user
        # Notes on members-only posts are for members of that community.
        members = Q(post__community__memberships__user=user) if user.is_authenticated else Q(pk__in=[])
        return qs.filter(Q(post__isnull=True) | members).distinct()

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        try:
            serializer.instance = services.create_note(author=self.request.user, **data)
        except ValueError as e:
            raise exceptions.PermissionDenied(str(e))
        except Exception as e:  # model validation (e.g. citation URLs)
            raise exceptions.ValidationError(getattr(e, "messages", [str(e)]))

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated])
    def rate(self, request, pk=None):
        note = self.get_object()
        ser = NoteRatingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            rating = services.rate(note, request.user, ser.validated_data["value"], ser.validated_data["tags"])
        except ValueError as e:
            raise exceptions.ValidationError(str(e))
        note.refresh_from_db(fields=["status"])
        return Response(
            {"rating": NoteRatingSerializer(rating).data, "note_status": note.status}, status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=["get"], permission_classes=[permissions.AllowAny])
    def public(self, request):
        qs = self.filter_queryset(self.get_queryset()).filter(status=CommunityNote.Status.HELPFUL)
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(PublicNoteSerializer(page, many=True).data)
