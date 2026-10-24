"""Responsible-journalism gates (JSN Journalist's Guidelines): human approval per language,
sensitive-topic checklist, opinion/advertising exclusion, flags in the review queue."""

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.agents.graph.nodes.assignment import assignment
from apps.agents.graph.nodes.standards import standards
from apps.agents.graph.text import classify_content
from apps.common.choices import ReviewStatus
from apps.editorial import services as ed
from apps.editorial.checklist import detect
from apps.editorial.models import ChecklistItem, ReviewTask, VerificationResult
from apps.feed.models import Snippet, SnippetVersion


@pytest.fixture
def editor(django_user_model):
    return django_user_model.objects.create_superuser(email="ed@example.com", password="x")


def make_snippet(risk="medium", langs=("fi", "en"), checklist=()):
    s = Snippet.objects.create(risk_tier=risk, confidence=0.9, review_status=ReviewStatus.PENDING_REVIEW)
    for lang in langs:
        SnippetVersion.objects.create(snippet=s, language=lang, headline=f"{lang} headline", review_status=ReviewStatus.PENDING_REVIEW,
                                      is_machine_translated=lang != "fi")
    for key in checklist:
        ChecklistItem.objects.create(snippet=s, key=key, label=f"{key} label", clauses="21–22")
    ed.enqueue(s, "new")
    return s


def task(s, language=None):
    return ReviewTask.objects.get(snippet=s, language=language, active=True)


@pytest.mark.django_db
def test_translation_waits_for_its_own_reviewer_even_at_medium_risk(editor):
    s = make_snippet("medium", ("fi", "en", "ar"))
    ed.approve(task(s), editor)
    s.refresh_from_db()
    status = dict(s.versions.values_list("language", "review_status"))
    assert s.review_status == ReviewStatus.PUBLISHED and status["fi"] == ReviewStatus.APPROVED
    assert status["en"] == ReviewStatus.PENDING_REVIEW and status["ar"] == ReviewStatus.PENDING_REVIEW
    ed.approve(task(s, "ar"), editor)
    assert s.versions.get(language="ar").review_status == ReviewStatus.APPROVED


@pytest.mark.django_db
def test_checklist_blocks_approval_and_publishing_until_confirmed(editor):
    s = make_snippet(checklist=("crime", "right_of_reply"))
    with pytest.raises(ValidationError, match="crime, right_of_reply"):
        ed.approve(task(s), editor)
    assert not ed.can_publish(s)
    with pytest.raises(ValidationError, match="right_of_reply"):
        ed.approve(task(s), editor, confirm=["crime"])  # partial confirmation is rolled back with the failed approval
    assert ChecklistItem.objects.get(snippet=s, key="crime").confirmed_at is None
    ed.approve(task(s), editor, confirm=["crime", "right_of_reply"], notes={"right_of_reply": "Club asked, no comment"})
    s.refresh_from_db()
    assert s.review_status == ReviewStatus.PUBLISHED
    item = ChecklistItem.objects.get(snippet=s, key="right_of_reply")
    assert item.confirmed_by == editor and item.note == "Club asked, no comment"
    assert s.audit_log.filter(action="checklist_confirmed").exists()


@pytest.mark.django_db
def test_batch_approve_skips_snippets_with_a_checklist(editor):
    s = make_snippet("low", ("fi",), checklist=("minors",))
    t = task(s)
    assert ed.batch_approve([t], editor)["skipped"] == [t.pk]


@pytest.mark.django_db
def test_review_queue_shows_flags(editor):
    s = make_snippet(checklist=("crime",))
    VerificationResult.objects.create(snippet=s, language="en", passed=False, confidence=0.4,
                                      mismatches=[{"kind": "language", "value": "", "issue": "text looks Swedish", "severity": "error"}])
    client = APIClient()
    client.force_authenticate(editor)
    tasks = {t["language"]: t for t in client.get("/api/editorial/tasks/").data["results"]}
    whole, en = tasks[None]["flags"], tasks["en"]["flags"]
    assert whole["checklist"][0]["key"] == "crime" and not whole["checklist"][0]["confirmed"]
    assert en["verification"][0]["issues"][0]["issue"] == "text looks Swedish" and en["checklist"] == []
    resp = client.post(f"/api/editorial/tasks/{tasks[None]['id']}/approve/", {}, format="json")
    assert resp.status_code == 400
    resp = client.post(f"/api/editorial/tasks/{tasks[None]['id']}/approve/", {"confirm": ["crime"]}, format="json")
    assert resp.status_code == 200


@pytest.mark.parametrize("title,body,expected", [
    ("Arvio: Viivi täytti Tarkastamon", "", "opinion"),
    ("Somejätit vastuuseen", "Pääkirjoitus lauantaille 24.10.", "opinion"),
    ("Liigan tila huolettaa", "kirjoittaa urheilutoimittaja kolumnissaan.", "opinion"),
    ("Uusi kahvila avautuu", "Kaupallinen yhteistyö: Kahvila X", "commercial"),
    ("Bussilinja 3 muuttuu", "Oulun joukkoliikenne muuttaa reittiä 1.12.", "news"),
    ("Fani arvioi uuden elokuvan", "Haastattelu", "news"),
])
def test_classify_content(title, body, expected):
    assert classify_content(title, body)[0] == expected


def test_assignment_excludes_opinion_and_commercial(settings):
    settings.LLM_MODEL = "stub"
    raw = [
        {"key": "a", "kind": "source", "title": "Bussilinja 3 muuttuu", "body": "Oulu", "content_type": "news"},
        {"key": "b", "kind": "source", "title": "Arvio: konsertti", "body": "", "content_type": "opinion", "content_marker": "arvio:"},
        {"key": "c", "kind": "source", "title": "Mainos", "body": "", "content_type": "commercial", "content_marker": "mainos"},
    ]
    out = assignment({"raw_items": raw, "community": {"name": "Oulu", "municipality": "Oulu"}, "max_items": 5})
    assert list(out["assignments"]) == ["a"]
    assert {e["key"]: e["content_type"] for e in out["excluded"]} == {"b": "opinion", "c": "commercial"}


def test_standards_flags_opinion_ads_and_sensitive_topics(settings):
    item = {"key": "k", "kind": "source", "url": "https://x", "publisher": "Kaleva",
            "title": "Poliisi epäilee seurajohtajaa kavalluksesta", "body": "14-vuotias pelaaja kertoi asiasta.", "content_type": "news"}
    draft = {"headline": "Kolumni: seura kriisissä", "summary": "Poliisi tutkii.", "key_facts": []}
    res = standards({"raw_items": [item], "drafts": {"k": draft}, "assignments": {"k": {"expires_at": "x"}}})["standards"]["k"]
    assert res["results"]["fact_vs_opinion"] == "fail" and not res["passed"]
    assert res["results"]["editorial_separated_from_ads"] == "pass"
    assert set(res["sensitive"]) == {"crime", "right_of_reply", "minors"}


def test_detect_is_quiet_on_neutral_news():
    assert detect("Oulun kaupunki avaa uuden kirjaston 1.12. Bussilinja 3 muuttuu.") == []
