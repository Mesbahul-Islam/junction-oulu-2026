from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import AgentRun
from .serializers import (
    AgentRunCreateSerializer,
    AgentRunDetailSerializer,
    AgentRunSerializer,
    SendSerializer,
)


class AgentRunViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Staff only: the AI newsroom's shifts.

    * ``POST /api/agents/runs/ {"max_stories": 4}`` starts a shift (202); 409 while one is going.
    * ``GET /api/agents/runs/<id>/`` is the live view: every desk's progress and every story's.
    * ``POST /api/agents/runs/<id>/send/ {"snippets": [..]}`` or ``{"all_ready": true}`` publishes
      stories marked Ready to send, in the name of the person who clicks.
    """

    permission_classes = [IsAdminUser]
    filterset_fields = ["status", "trigger"]

    def get_queryset(self):
        qs = AgentRun.objects.select_related("community").prefetch_related("stories")
        if self.action == "retrieve":
            qs = qs.prefetch_related("steps", "stories__snippet", "stories__source_document")
        return qs

    def get_serializer_class(self):
        return AgentRunDetailSerializer if self.action == "retrieve" else AgentRunSerializer

    def list(self, request, *args, **kwargs):
        services.close_stale_runs()
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        from .tasks import run_newsroom

        ser = AgentRunCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        services.close_stale_runs()
        if services.busy():
            return Response({"detail": "A newsroom run is already going. Wait for it to finish."}, status=409)
        try:
            run = services.create_run(AgentRun.Trigger.MANUAL, ser.validated_data.get("max_stories"))
        except ValidationError as exc:
            return Response({"detail": exc.messages[0]}, status=400)
        transaction.on_commit(lambda: run_newsroom.delay(run.pk))
        return Response(AgentRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        ser = SendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        run = self.get_object()
        stories = [s for s in run.stories.select_related("snippet") if s.snippet_id]
        if ser.validated_data["all_ready"]:
            snippets = [s.snippet for s in stories if s.snippet.review_level == "ready"]
        else:
            wanted = set(ser.validated_data["snippets"])
            snippets = [s.snippet for s in stories if s.snippet_id in wanted]
        sent, refused = [], []
        for snippet in snippets:
            try:
                (sent if services.send_story(snippet, request.user) else refused).append(snippet.pk)
            except ValidationError:
                refused.append(snippet.pk)
        return Response({"sent": sent, "refused": refused})


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
        services.close_stale_runs()
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
            # Only communities with their own feeds can be run (topic communities have none).
            "communities": [{"id": c.pk, "name": c.name, "slug": c.slug}
                            for c in CommunityGroup.objects.filter(is_active=True, source_feeds__is_active=True).distinct()],
        })
