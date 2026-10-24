"""Admin dashboard APIs: overview, preview a reader's feed, readers list, scheduler overlap guard."""

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.agents import tasks
from apps.agents.models import AgentRun
from apps.common.choices import ReviewStatus
from apps.communities.models import CommunityGroup, SourceFeed
from apps.feed.models import Snippet, SnippetVersion


@pytest.fixture
def staff(django_user_model):
    client = APIClient()
    client.force_authenticate(django_user_model.objects.create_superuser(email="ed@example.com", password="x"))
    return client


@pytest.fixture
def oulu(db):
    c = CommunityGroup.objects.create(name="Oulu", slug="oulu")
    SourceFeed.objects.create(community=c, name="Kaleva", url="https://example.invalid/rss", kind="rss")
    return c


def test_dashboard_is_staff_only_and_reports_schedule_and_counts(staff, oulu, settings, django_user_model):
    settings.LLM_MODEL = "stub"
    reader = APIClient()
    reader.force_authenticate(django_user_model.objects.create_user(email="r@example.com"))
    assert reader.get("/api/agents/dashboard/").status_code == 403
    d = staff.get("/api/agents/dashboard/").data
    assert d["schedule"]["every_minutes"] == settings.AGENT_SCHEDULE_MINUTES
    assert set(d["counts"]) >= {"editor_tasks", "translation_tasks", "checklist_pending", "flagged_posts", "published_24h"}
    assert d["llm"][0]["stub_reason"] and d["communities"][0]["slug"] == "oulu"


def test_staff_preview_feed_as_reader_uses_their_language(staff, django_user_model):
    s = Snippet.objects.create(review_status=ReviewStatus.PUBLISHED, published_at=timezone.now())
    for lang in ("fi", "uk"):
        SnippetVersion.objects.create(snippet=s, language=lang, headline=f"{lang} h", review_status=ReviewStatus.APPROVED)
    uk_reader = django_user_model.objects.create_user(email="u@example.com", preferred_language="uk", onboarded=True)
    assert staff.get(f"/api/feed/snippets/?as_user={uk_reader.pk}").data["results"][0]["language"] == "uk"
    # Non-staff can't preview someone else's feed: the parameter is ignored.
    other = APIClient()
    other.force_authenticate(django_user_model.objects.create_user(email="f@example.com", preferred_language="fi"))
    assert other.get(f"/api/feed/snippets/?as_user={uk_reader.pk}").data["results"][0]["language"] == "fi"
    assert [r["email"] for r in staff.get("/api/accounts/readers/").data] == ["u@example.com"]
    assert other.get("/api/accounts/readers/").status_code == 403


def test_scheduled_run_skips_a_community_whose_run_is_still_going(oulu, monkeypatch):
    queued = []
    monkeypatch.setattr(tasks.ingest_and_run, "delay", lambda *a, **kw: queued.append(a))
    busy = AgentRun.objects.create(community=oulu, status=AgentRun.Status.RUNNING)
    assert tasks.ingest_all_communities() == [] and queued == []
    # A run stuck for hours (worker restarted) is closed, and the community runs again.
    AgentRun.objects.filter(pk=busy.pk).update(created_at=timezone.now() - timedelta(hours=3))
    assert tasks.ingest_all_communities() == [oulu.pk]
    assert AgentRun.objects.get(pk=busy.pk).status == AgentRun.Status.FAILED
