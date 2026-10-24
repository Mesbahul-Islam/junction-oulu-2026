from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

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


class DashboardView(APIView):
    """GET /api/agents/dashboard/ (staff): everything the admin overview shows, in one call."""

    permission_classes = [IsAdminUser]

    @staticmethod
    def _llm_status(llm) -> list[dict]:
        """Each agent's model, checked against the Ollama server when that's the provider."""
        rows, checked = [], {}
        for agent in llm.AGENTS:
            info = {k: v for k, v in llm.resolve(agent).items() if k != "api_key"}
            if info["provider"] == "ollama" and not info["stub_reason"]:
                key = (info["model"], info["base_url"])
                checked.setdefault(key, llm.ollama_model_problem(info))
                info["stub_reason"] = checked[key]
            rows.append(info)
        return rows

    def get(self, request):
        from datetime import timedelta

        from django.apps import apps as django_apps
        from django.conf import settings
        from django.utils import timezone

        from .graph import llm

        now = timezone.now()
        day = now - timedelta(hours=24)
        ReviewTask = django_apps.get_model("editorial", "ReviewTask")
        ChecklistItem = django_apps.get_model("editorial", "ChecklistItem")
        Snippet = django_apps.get_model("feed", "Snippet")
        Post = django_apps.get_model("communities", "Post")
        CommunityGroup = django_apps.get_model("communities", "CommunityGroup")
        open_tasks = ReviewTask.objects.filter(active=True, status="open")

        minutes = settings.AGENT_SCHEDULE_MINUTES
        last_scheduled = AgentRun.objects.filter(trigger=AgentRun.Trigger.SCHEDULE).order_by("-created_at").first()
        next_run = None
        try:
            from django_celery_beat.models import PeriodicTask

            beat = PeriodicTask.objects.filter(task="apps.agents.tasks.ingest_all_communities", enabled=True).first()
            if beat and beat.last_run_at:
                next_run = beat.last_run_at + timedelta(minutes=minutes)
        except Exception:
            pass
        if next_run is None and last_scheduled:
            next_run = last_scheduled.created_at + timedelta(minutes=minutes)

        runs = AgentRun.objects.filter(created_at__gte=day)
        return Response({
            "schedule": {
                "every_minutes": minutes,
                "max_stories_per_run": settings.AGENT_MAX_ITEMS,
                "last_scheduled_run_at": last_scheduled.created_at if last_scheduled else None,
                "next_run_at": next_run,
            },
            "counts": {
                "editor_tasks": open_tasks.filter(language__isnull=True).count(),
                "translation_tasks": open_tasks.filter(language__isnull=False).count(),
                "checklist_pending": ChecklistItem.objects.filter(confirmed_at__isnull=True).count(),
                "published_24h": Snippet.objects.filter(published_at__gte=day).count(),
                "flagged_posts": Post.objects.filter(status=Post.Status.HIDDEN).count(),
                "runs_24h": runs.count(),
                "failed_runs_24h": runs.filter(status=AgentRun.Status.FAILED).count(),
            },
            "running": AgentRunSerializer(AgentRun.objects.filter(status__in=["queued", "running"]), many=True).data,
            "llm": self._llm_status(llm),
            "communities": [{"id": c.pk, "name": c.name, "slug": c.slug} for c in CommunityGroup.objects.filter(is_active=True)],
        })
