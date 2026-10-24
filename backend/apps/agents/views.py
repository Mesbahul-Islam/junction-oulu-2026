from django.core.exceptions import ValidationError
from django.db import transaction
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, IsAuthenticated
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


class ShortlistViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Members decide what the newsroom covers next.

    * ``GET /api/agents/shortlist/``: open stories, in the reader's language, most-voted first,
      plus the voted stories the newsroom recently covered.
    * ``POST`` / ``DELETE /api/agents/shortlist/<id>/vote/``: vote, or take the vote back.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        from django.db.models import Count, Exists, OuterRef

        from .models import CoverageCandidate, CoverageVote

        return (CoverageCandidate.objects.filter(community=services.newsroom_community())
                .select_related("source_document", "covered_by__snippet")
                .annotate(n_votes=Count("votes"),
                          voted=Exists(CoverageVote.objects.filter(candidate=OuterRef("pk"), user=self.request.user))))

    def list(self, request, *args, **kwargs):
        from apps.feed.services import language_chain, requester_language

        from .models import CoverageCandidate

        chain = language_chain(requester_language(request))
        qs = self.get_queryset()
        open_ = qs.filter(status=CoverageCandidate.Status.OPEN).order_by("-n_votes", "-jev_score")
        covered = qs.filter(status=CoverageCandidate.Status.COVERED, n_votes__gt=0).order_by("-updated_at")[:5]
        return Response({
            "open": [self._card(c, chain) for c in open_],
            "covered": [self._card(c, chain) for c in covered],
            "member": request.user.memberships.exists(),
        })

    @staticmethod
    def _card(c, chain) -> dict:
        titles = c.titles or {}
        lang = next((code for code in chain if titles.get(code)), "fi")
        doc = c.source_document
        snippet = c.covered_by.snippet if c.covered_by_id and c.covered_by.snippet_id else None
        return {
            "id": c.pk, "title": titles.get(lang) or doc.title, "language": lang, "original_title": doc.title,
            "translated": lang != "fi", "url": doc.url, "image_url": doc.image_url or None,
            "votes": c.n_votes, "voted": c.voted, "status": c.status, "reasons": c.reasons,
            "story": snippet.pk if snippet and snippet.published_at else None,
        }

    @action(detail=True, methods=["post", "delete"])
    def vote(self, request, pk=None):
        from .models import CoverageCandidate, CoverageVote

        cand = self.get_object()
        if cand.status != CoverageCandidate.Status.OPEN:
            return Response({"detail": "Voting on this story has closed."}, status=400)
        if not request.user.memberships.exists():
            return Response({"detail": "Join a community to vote on what the newsroom covers."}, status=403)
        if request.method == "POST":
            CoverageVote.objects.get_or_create(candidate=cand, user=request.user)
        else:
            CoverageVote.objects.filter(candidate=cand, user=request.user).delete()
        return Response({"votes": cand.votes.count(), "voted": request.method == "POST"})


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
        from .newsroom import wire
        from .newsroom.runner import target_languages

        now = timezone.now()
        day = now - timedelta(hours=24)
        ChecklistItem = django_apps.get_model("editorial", "ChecklistItem")
        Snippet = django_apps.get_model("feed", "Snippet")
        Post = django_apps.get_model("communities", "Post")

        from apps.editorial.services import queue_for
        from apps.communities.services import can_moderate

        open_tasks = queue_for(request.user).filter(status="open")

        from django_celery_beat.models import PeriodicTask

        minutes = settings.AGENT_SCHEDULE_MINUTES
        last_scheduled = AgentRun.objects.filter(trigger=AgentRun.Trigger.SCHEDULE).order_by("-created_at").first()
        beat = (PeriodicTask.objects.filter(task="apps.agents.tasks.ingest_all_communities")
                .select_related("interval", "crontab", "clocked", "solar").first())
        enabled = bool(beat and beat.enabled)
        next_run = None
        if beat and beat.interval:
            interval = beat.interval.schedule.run_every
            minutes = interval.total_seconds() / 60
            if enabled and beat.last_run_at:
                next_run = beat.last_run_at + interval
        elif beat:
            minutes = None
        community = services.newsroom_community()

        runs = AgentRun.objects.filter(created_at__gte=day)
        return Response({
            "schedule": {
                "every_minutes": minutes,
                "enabled": enabled,
                "description": str(beat.schedule) if beat else "Not registered",
                "last_dispatched_at": beat.last_run_at if beat else None,
                "max_stories_per_run": settings.AGENT_MAX_ITEMS,
                "last_scheduled_run_at": last_scheduled.created_at if last_scheduled else None,
                "next_run_at": next_run,
            },
            "counts": {
                "editor_tasks": open_tasks.filter(language__isnull=True).count(),
                "translation_tasks": open_tasks.filter(language__isnull=False).count(),
                "checklist_pending": ChecklistItem.objects.filter(
                    confirmed_at__isnull=True,
                    snippet_id__in=open_tasks.filter(language__isnull=True).values("snippet_id"),
                ).count(),
                "published_24h": Snippet.objects.filter(published_at__gte=day).count(),
                "flagged_posts": sum(1 for post in Post.objects.filter(status=Post.Status.HIDDEN).select_related("community")
                                     if can_moderate(request.user, post.community)),
                "runs_24h": runs.count(),
                "failed_runs_24h": runs.filter(status=AgentRun.Status.FAILED).count(),
            },
            "running": AgentRunSerializer(AgentRun.objects.filter(status__in=["queued", "running"]), many=True).data,
            "llm": self._llm_status(llm),
            # The newsroom runs for one community; the Kaleva feed is fixed in wire.py.
            "communities": [{"id": community.pk, "name": community.name, "slug": community.slug}] if community else [],
            "settings": {
                "source": {
                    "name": wire.KALEVA_FEED_NAME, "url": wire.KALEVA_FEED_URL,
                    "max_entries": wire.MAX_ENTRIES_PER_FEED,
                    "candidate_hours": wire.CANDIDATE_HOURS, "max_candidates": wire.MAX_CANDIDATES,
                },
                "languages": target_languages(community) if community else [],
                "ranking": {
                    "feed_ranker": settings.FEED_RANKER,
                    "jev_configured": bool(settings.TYPESAFE_API_KEY), "model": settings.JEV_MODEL,
                    "top_k": settings.JEV_TOP_K, "weight": settings.JEV_WEIGHT,
                    "timeout_seconds": settings.JEV_TIMEOUT, "cache_seconds": settings.JEV_CACHE_SECONDS,
                },
                "credentials": {provider: bool(key) for provider, key in settings.LLM_API_KEYS.items()},
                "shared_model_key_configured": bool(settings.LLM_API_KEY),
                "confidence_threshold": settings.AGENT_CONFIDENCE_THRESHOLD,
                "timezone": settings.TIME_ZONE,
                "tasks_eager": settings.CELERY_TASK_ALWAYS_EAGER,
            },
        })
