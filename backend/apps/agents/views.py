from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from .models import AgentRun
from .serializers import (
    AgentRunCreateSerializer,
    AgentRunDetailSerializer,
    AgentRunSerializer,
)


class AgentRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Staff-only: list/inspect agent runs and trigger a new one (FR-3.1/3.2).

    POST /api/agents/runs/ ``{"community": 1, "source_ids": [..]?, "language_targets": [..]?, "max_items": 5?}``
    queues ``ingest_and_run`` (or ``run_graph_for_sources`` when ``source_ids``
    are given) via Celery and returns the queued run (202).
    """

    permission_classes = [IsAdminUser]
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
