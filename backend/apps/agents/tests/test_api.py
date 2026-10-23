import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.agents.models import AgentRun

pytestmark = pytest.mark.django_db


@pytest.fixture
def community():
    return apps.get_model("communities", "CommunityGroup").objects.create(name="Oulu", slug="oulu", languages=["fi", "en"])


@pytest.fixture
def staff_client():
    user = get_user_model().objects.create_user(email="staff@example.com", password="x-test-pass-1", is_staff=True)
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_trigger_run_is_staff_only_and_async(community, staff_client, monkeypatch, django_capture_on_commit_callbacks):
    calls = []
    monkeypatch.setattr("apps.agents.tasks.ingest_and_run.delay", lambda *a, **kw: calls.append((a, kw)))

    assert APIClient().post("/api/agents/runs/", {"community": community.pk}, format="json").status_code in (401, 403)

    with django_capture_on_commit_callbacks(execute=True):
        resp = staff_client.post("/api/agents/runs/", {"community": community.pk, "max_items": 3}, format="json")
    assert resp.status_code == 202, resp.content
    run = AgentRun.objects.get(pk=resp.json()["id"])
    assert run.status == "queued" and calls and calls[0][1]["run_id"] == run.pk

    assert staff_client.get("/api/agents/runs/").status_code == 200
    detail = staff_client.get(f"/api/agents/runs/{run.pk}/").json()
    assert detail["steps"] == []


def test_webhook_requires_token(community, settings):
    settings.AGENT_WEBHOOK_TOKEN = "s3cret"
    run = AgentRun.objects.create(community=community)
    client = APIClient()
    body = {"run_id": run.pk, "status": "failed", "error": "worker crashed"}
    assert client.post("/api/agents/webhook/complete/", body, format="json").status_code == 403
    resp = client.post("/api/agents/webhook/complete/", body, format="json", HTTP_X_AGENT_TOKEN="s3cret")
    assert resp.status_code == 200
    run.refresh_from_db()
    assert run.status == "failed" and run.error == "worker crashed"
