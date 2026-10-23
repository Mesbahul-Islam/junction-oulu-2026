"""FR-3.9: each reader gets the snippet in their profile language, with the Finnish original alongside."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.common.choices import ReviewStatus
from apps.feed.models import Snippet, SnippetVersion


@pytest.fixture
def snippet(db):
    s = Snippet.objects.create(review_status=ReviewStatus.PUBLISHED, published_at=timezone.now())
    for lang, headline in [("fi", "Bussi 3 muuttuu"), ("uk", "Автобус 3 змінюється"), ("en", "Bus 3 changes")]:
        SnippetVersion.objects.create(
            snippet=s, language=lang, headline=headline, review_status=ReviewStatus.APPROVED,
            explainer={"newcomer": f"{lang}: check your route", "student": f"{lang}: student note"},
        )
    return s


def _card(user=None, **headers):
    client = APIClient()
    if user:
        client.force_authenticate(user)
    return client.get("/api/feed/snippets/", **headers).data["results"][0]


def test_reader_gets_profile_language_and_original(snippet, django_user_model):
    reader = django_user_model.objects.create_user(email="u@example.com", preferred_language="uk", reader_situation="newcomer")
    card = _card(reader)
    assert card["language"] == "uk" and card["in_your_language"]
    assert card["headline"] == "Автобус 3 змінюється"
    assert card["for_you"] == "uk: check your route"
    assert card["original"]["language"] == "fi" and card["original"]["headline"] == "Bussi 3 muuttuu"


def test_missing_language_falls_back_to_english_and_says_so(snippet, django_user_model):
    reader = django_user_model.objects.create_user(email="r@example.com", preferred_language="ru", reader_situation="student")
    card = _card(reader)
    assert card["language"] == "en" and not card["in_your_language"] and card["requested_language"] == "ru"
    assert card["for_you"] == "en: student note"


def test_finnish_reader_has_no_separate_original(snippet, django_user_model):
    reader = django_user_model.objects.create_user(email="f@example.com", preferred_language="fi")
    card = _card(reader)
    assert card["language"] == "fi" and card["original"] is None


def test_anonymous_uses_browser_language(snippet):
    assert _card(HTTP_ACCEPT_LANGUAGE="uk-UA,uk;q=0.9")["language"] == "uk"


def test_for_you_falls_back_to_original_when_translation_lacks_it(snippet, django_user_model):
    snippet.versions.filter(language="uk").update(explainer={})
    reader = django_user_model.objects.create_user(email="n@example.com", preferred_language="uk", reader_situation="newcomer")
    card = _card(reader)
    assert card["for_you"] == "fi: check your route" and card["for_you_language"] == "fi"
