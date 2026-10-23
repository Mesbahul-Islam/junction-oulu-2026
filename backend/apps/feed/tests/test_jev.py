"""Jev re-ranking (FR-2.3) with a fake TypeSafe client: no API key or network needed."""

from types import SimpleNamespace

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.common.choices import ReviewStatus
from apps.feed import jev, recommend, services
from apps.feed.models import Snippet, SnippetVersion

CHAIN = ["fi", "en"]


class FakeClient:
    """Stands in for typesafe_sdk.TypeSafeClient. `relevance` maps headline -> noul."""

    def __init__(self, relevance, fail=False):
        self.relevance, self.fail, self.calls = relevance, fail, 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def system_one(self, state, questions):
        self.calls += 1
        if self.fail:
            raise RuntimeError("Jev is down")
        p = self.relevance[state["news"]["headline"]]
        noul = SimpleNamespace(noul=p)
        return SimpleNamespace(
            nouls={"affects_reader": noul, "matches_interests": noul, "needs_action": noul},
            scores={"urgency": SimpleNamespace(score=3 * p)},
        )


@pytest.fixture(autouse=True)
def jev_on(settings):
    settings.TYPESAFE_API_KEY = "test-key"
    settings.FEED_RANKER = "jev"
    cache.clear()


@pytest.fixture
def reader(django_user_model):
    return django_user_model.objects.create_user(
        email="reader@example.com", password="x", reader_situation="newcomer"
    )


def _published(headline, minutes_old):
    now = timezone.now()
    s = Snippet.objects.create(
        review_status=ReviewStatus.PUBLISHED, published_at=now - timezone.timedelta(minutes=minutes_old)
    )
    SnippetVersion.objects.create(snippet=s, language="fi", headline=headline, review_status=ReviewStatus.APPROVED)
    return s


@pytest.fixture
def ranked(monkeypatch):
    def run(user, client):
        monkeypatch.setattr(jev, "make_client", lambda: client)
        return recommend.rank(services.feed_candidates(CHAIN), user, chain=CHAIN)

    return run


def test_combine_weights():
    assert jev.combine({"affects_reader": 1, "matches_interests": 1, "needs_action": 1, "urgency": 3}) == pytest.approx(1)
    assert jev.combine({"affects_reader": 0, "matches_interests": 0, "needs_action": 0, "urgency": 0}) == 0


@pytest.mark.django_db
def test_jev_reorders_shortlist(reader, ranked):
    newer = _published("Uutinen A", minutes_old=1)  # heuristic prefers the fresher one
    older = _published("Kela muuttaa ohjeita", minutes_old=600)
    client = FakeClient({"Uutinen A": 0.05, "Kela muuttaa ohjeita": 0.95})

    feed = ranked(reader, client)

    assert [s.pk for s in feed] == [older.pk, newer.pk]
    assert feed[0].ranking["ranker"] == "jev"
    assert feed[0].ranking["jev"]["affects_reader"] == 0.95


@pytest.mark.django_db
def test_jev_failure_falls_back_to_heuristic(reader, ranked):
    newer = _published("Uutinen A", minutes_old=1)
    older = _published("Kela muuttaa ohjeita", minutes_old=600)

    feed = ranked(reader, FakeClient({}, fail=True))

    assert [s.pk for s in feed] == [newer.pk, older.pk]
    assert all(s.ranking["ranker"] == "heuristic" for s in feed)


@pytest.mark.django_db
def test_answers_are_cached(reader, ranked):
    _published("Uutinen A", minutes_old=1)
    client = FakeClient({"Uutinen A": 0.5})
    ranked(reader, client)
    ranked(reader, client)
    assert client.calls == 1


@pytest.mark.django_db
def test_anonymous_and_no_key_use_heuristic(reader, settings):
    _published("Uutinen A", minutes_old=1)
    from django.contrib.auth.models import AnonymousUser

    ranked = recommend.rank(services.feed_candidates(CHAIN), AnonymousUser(), chain=CHAIN)
    assert ranked[0].ranking["ranker"] == "heuristic"

    settings.TYPESAFE_API_KEY = ""
    ranked = recommend.rank(services.feed_candidates(CHAIN), reader, chain=CHAIN)
    assert ranked[0].ranking["ranker"] == "heuristic"


@pytest.mark.django_db
def test_reader_state_has_no_identifiers(reader):
    state = jev.reader_state(reader)
    assert "reader@example.com" not in str(state)
    assert state["situation"] == "newcomer"
