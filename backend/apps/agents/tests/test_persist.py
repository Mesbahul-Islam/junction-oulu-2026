"""DB test: offline graph result -> Snippet / SnippetVersion / verification rows,
editorial queue, nothing published. Also exercises scout's DB path with
pre-seeded SourceDocuments (no network)."""

import pytest
from django.apps import apps

from apps.agents import services
from apps.agents.graph.build import build_graph
from apps.agents.models import AgentRun

from .test_graph_smoke import _state

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _force_stub(settings):
    settings.GEMINI_API_KEY = ""
    settings.AGENT_CONFIDENCE_THRESHOLD = 0.7


@pytest.fixture
def community():
    CommunityGroup = apps.get_model("communities", "CommunityGroup")
    return CommunityGroup.objects.create(
        name="Oulu", slug="oulu", municipality="Oulu", bbox=[25.3, 64.9, 25.7, 65.1], languages=["fi", "en", "se"]
    )


def test_persist_creates_pending_snippets(community):
    run = AgentRun.objects.create(community=community, trigger=AgentRun.Trigger.MANUAL)
    state = _state()
    state["community_id"] = community.pk
    state["language_targets"] = ["en", "se"]
    final = build_graph().invoke(state)
    snippets = services.persist_graph_result(run, final)

    assert len(snippets) == 2
    for s in snippets:
        s.refresh_from_db()
        assert s.review_status == "pending_review" and s.ai_generated and s.published_at is None
        langs = dict(s.versions.values_list("language", "is_machine_translated"))
        assert langs == {"fi": False, "en": True, "se": False}
        se = s.versions.get(language="se")
        assert se.summary == "" and se.review_status == "draft"
        assert s.verification_results.exists() and s.standards_checks.exists()
        assert s.review_tasks.exists()
    # the community tip has no official source -> failed verification -> escalated to high
    tip = next(s for s in snippets if s.source_documents.count() == 0)
    assert tip.risk_tier == "high"
    assert run.state["drafts"]


def test_run_graph_for_sources_end_to_end(community):
    SourceDocument = apps.get_model("feed", "SourceDocument")
    doc = SourceDocument.objects.create(
        url="https://www.ouka.fi/uutiset/1", title="Kirjaston aukioloajat muuttuvat",
        body="Pääkirjasto on auki 1.12.2026 alkaen klo 10.00-18.00.", publisher="Oulun kaupunki",
        content_hash="abc", version=1,
    )
    from apps.agents.tasks import run_graph_for_sources

    result = run_graph_for_sources(community.pk, [doc.pk])
    run = AgentRun.objects.get(pk=result["run_id"])
    assert run.status == "succeeded", run.error
    assert run.steps.count() == 8
    assert len(result["snippets"]) == 1
