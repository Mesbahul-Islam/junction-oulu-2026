"""Community Notes API (FR-4)."""

from rest_framework import exceptions, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response

from . import services
from .models import CommunityNote
from .serializers import CommunityNoteSerializer, NoteRatingSerializer, PublicNoteSerializer


class NotePagination(CursorPagination):
    ordering = "-created_at"


class CommunityNoteViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet
):
    """GET/POST /api/notes/notes/ (?snippet=, ?post=, ?status=) — all notes, for raters.
    POST /api/notes/notes/{id}/rate/ {value, tags[]} — upsert rating, recomputes status.
    GET /api/notes/notes/public/ (?snippet=, ?post=) — helpful notes only."""

    serializer_class = CommunityNoteSerializer
    pagination_class = NotePagination
    filterset_fields = ["snippet", "post", "status"]

    def get_queryset(self):
        # TODO: hide notes on members-only posts from non-members.
        return CommunityNote.objects.all()

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

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
