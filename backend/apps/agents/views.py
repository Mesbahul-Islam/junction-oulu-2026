import hmac

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import AgentRun
from .serializers import (
    AgentRunCreateSerializer,
    AgentRunDetailSerializer,
    AgentRunSerializer,
    WebhookCompleteSerializer,
)


class RunPagination(CursorPagination):
    ordering = "-created_at"


class AgentRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Staff-only: list/inspect agent runs and trigger a new one (FR-3.1/3.2).

    POST /api/agents/runs/ ``{"community": 1, "source_ids": [..]?, "language_targets": [..]?, "max_items": 5?}``
    queues ``ingest_and_run`` (or ``run_graph_for_sources`` when ``source_ids``
    are given) via Celery and returns the queued run (202).
    """

    permission_classes = [IsAdminUser]
    pagination_class = RunPagination
    filterset_fields = ["community", "status", "trigger"]

    def get_queryset(self):
        qs = AgentRun.objects.select_related("community")
        if self.action == "retrieve":
            qs = qs.prefetch_related("steps")
        return qs

    def get_serializer_class(self):
        if self.action == "retrieve":
            return AgentRunDetailSerializer
        if self.action == "create":
            return AgentRunCreateSerializer
        return AgentRunSerializer

    def create(self, request, *args, **kwargs):
        from .tasks import ingest_and_run, run_graph_for_sources

        ser = AgentRunCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        options = {k: data[k] for k in ("language_targets", "max_items") if k in data}
        run = AgentRun.objects.create(community_id=data["community"], trigger=AgentRun.Trigger.MANUAL)

        def _queue():
            if data.get("source_ids"):
                run_graph_for_sources.delay(data["community"], data["source_ids"], run_id=run.pk, **options)
            else:
                ingest_and_run.delay(data["community"], run_id=run.pk, trigger=AgentRun.Trigger.MANUAL, **options)

        transaction.on_commit(_queue)
        return Response(AgentRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)


class WebhookCompleteView(APIView):
    """FR-3.3 stub: an external agent worker reports a finished run.

    Auth: header ``X-Agent-Token: <settings.AGENT_WEBHOOK_TOKEN>`` (or
    ``Authorization: Bearer <token>``). Disabled when the setting is empty.
    Body: ``{"run_id": 1, "status": "succeeded"|"failed", "state": {...}?, "error": ""?}``.
    A succeeded callback carrying a graph ``state`` with ``drafts`` is persisted
    for review exactly like a local run (nothing is published).
    """

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def _authorized(self, request) -> bool:
        expected = getattr(settings, "AGENT_WEBHOOK_TOKEN", "") or ""
        if not expected:
            return False
        token = request.headers.get("X-Agent-Token", "")
        auth = request.headers.get("Authorization", "")
        if not token and auth.lower().startswith("bearer "):
            token = auth[7:].strip()
        return bool(token) and hmac.compare_digest(token.encode(), expected.encode())

    def post(self, request):
        if not self._authorized(request):
            return Response({"detail": "Invalid or missing agent token."}, status=status.HTTP_403_FORBIDDEN)
        ser = WebhookCompleteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        try:
            run = AgentRun.objects.get(pk=data["run_id"])
        except AgentRun.DoesNotExist:
            return Response({"detail": "Unknown run."}, status=status.HTTP_404_NOT_FOUND)

        snippet_ids: list[int] = []
        if data["status"] == AgentRun.Status.SUCCEEDED and (data.get("state") or {}).get("drafts"):
            state = dict(data["state"])
            state.setdefault("community_id", run.community_id)
            snippet_ids = [s.pk for s in services.persist_graph_result(run, state)]
        elif data.get("state"):
            run.state = data["state"]
        run.status = data["status"]
        run.error = data.get("error", "") or ""
        run.finished_at = timezone.now()
        run.save()
        return Response({"run_id": run.pk, "status": run.status, "snippets": snippet_ids})
