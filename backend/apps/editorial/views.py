"""Editorial API: review queue and decisions (FR-3.4, FR-3.7), audit trail and public
corrections log (FR-3.13)."""

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import exceptions, generics, mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import CursorPagination, LimitOffsetPagination
from rest_framework.response import Response

from . import services
from .models import AuditLogEntry, Correction, ReviewTask
from .serializers import (
    ApproveSerializer,
    AuditLogEntrySerializer,
    BatchApproveSerializer,
    CommentInputSerializer,
    CorrectionSerializer,
    ReviewTaskSerializer,
)

REVIEWER_ROLES = ("news_editor", "editor", "standards_editor", "language_reviewer", "community_editor", "admin")


class IsReviewer(permissions.BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and (u.is_superuser or u.roles.filter(role__in=REVIEWER_ROLES).exists()))


def _call(fn, *args, **kwargs):
    """Map service-layer Django exceptions to DRF responses."""
    try:
        return fn(*args, **kwargs)
    except DjangoPermissionDenied as e:
        raise exceptions.PermissionDenied(str(e))
    except DjangoValidationError as e:
        raise exceptions.ValidationError(e.messages)


class QueuePagination(LimitOffsetPagination):
    default_limit = 50


class ReviewTaskViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /api/editorial/tasks/ — queue, highest priority (reports/flags) first.
    Filters: ?role=, ?language=, ?community=<slug|id>, ?status= (default open), ?reason=."""

    serializer_class = ReviewTaskSerializer
    permission_classes = [IsReviewer]
    pagination_class = QueuePagination
    filter_backends: list = []

    def get_queryset(self):
        qs = services.queue_for(self.request.user).prefetch_related("snippet__versions")
        p = self.request.query_params
        if self.action == "list":
            qs = qs.filter(status=p.get("status", ReviewTask.Status.OPEN))
        if p.get("role"):
            qs = qs.filter(required_role=p["role"])
        if p.get("language"):
            qs = qs.filter(language=p["language"])
        if p.get("reason"):
            qs = qs.filter(reason=p["reason"])
        if c := p.get("community"):
            qs = qs.filter(snippet__community_id=int(c)) if c.isdigit() else qs.filter(snippet__community__slug=c)
        return qs.order_by("-priority", "created_at")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        ser = ApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = _call(services.approve, self.get_object(), request.user, edits=ser.validated_data.get("edits"))
        return Response(ReviewTaskSerializer(task).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        ser = CommentInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = _call(services.reject, self.get_object(), request.user, ser.validated_data["comment"])
        return Response(ReviewTaskSerializer(task).data)

    @action(detail=True, methods=["post"], url_path="request-changes")
    def request_changes(self, request, pk=None):
        ser = CommentInputSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        task = _call(services.request_changes, self.get_object(), request.user, ser.validated_data["comment"])
        return Response(ReviewTaskSerializer(task).data)

    @action(detail=False, methods=["post"], url_path="batch-approve")
    def batch_approve(self, request):
        """FR-3.7 Low tier: approve many batch_low_risk tasks in one call."""
        ser = BatchApproveSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        tasks = self.get_queryset().filter(pk__in=ser.validated_data["task_ids"], status=ReviewTask.Status.OPEN)
        return Response(services.batch_approve(list(tasks), request.user))


class SnippetAuditView(generics.ListAPIView):
    """GET /api/editorial/snippets/{snippet_id}/audit/ — full agent + human trail (FR-3.13)."""

    serializer_class = AuditLogEntrySerializer
    permission_classes = [IsReviewer]
    pagination_class = None
    filter_backends: list = []

    def get_queryset(self):
        return AuditLogEntry.objects.filter(snippet_id=self.kwargs["snippet_id"]).select_related("actor")


class CorrectionPagination(CursorPagination):
    ordering = "-published_at"


class CorrectionViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/editorial/corrections/ — public corrections log (FR-3.13). ?snippet= filter."""

    serializer_class = CorrectionSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = CorrectionPagination
    filterset_fields = ["snippet", "language"]

    def get_queryset(self):
        return Correction.objects.filter(published_at__isnull=False)
