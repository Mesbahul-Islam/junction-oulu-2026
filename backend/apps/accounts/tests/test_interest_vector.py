"""The ranking weights (interest_vector) follow the profile's interests, however they change."""

import pytest
from django.utils import timezone

from apps.accounts.models import Interest
from apps.accounts.services import complete_onboarding
from apps.common.choices import ReviewStatus
from apps.feed import recommend
from apps.feed.models import Snippet


@pytest.fixture
def interests(db):
    return {slug: Interest.objects.get_or_create(slug=slug, defaults={"name": slug.title()})[0] for slug in ("sports", "housing", "work")}


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(email="r@example.com")


def vector(user):
    user.profile.refresh_from_db()
    return user.profile.interest_vector


def test_set_add_remove_keep_learned_weights(user, interests):
    user.profile.interests.set([interests["sports"], interests["housing"]])
    assert vector(user) == {"sports": 1.0, "housing": 1.0}

    user.profile.interest_vector = {"sports": 2.5, "housing": 1.0}  # e.g. learned from engagement
    user.profile.save()
    user.profile.interests.add(interests["work"])
    user.profile.interests.remove(interests["housing"])
    assert vector(user) == {"sports": 2.5, "work": 1.0}

    user.profile.interests.clear()
    assert vector(user) == {}


def test_changes_from_the_interest_side(user, interests):
    interests["sports"].profiles.add(user.profile)
    assert vector(user) == {"sports": 1.0}
    interests["sports"].profiles.clear()
    assert vector(user) == {}


def test_onboarding_sets_weights(user, interests):
    complete_onboarding(user, {"interests": ["work", "housing"], "reader_situation": "newcomer"})
    assert vector(user) == {"work": 1.0, "housing": 1.0}


def test_ranking_uses_each_readers_interests(django_user_model, interests):
    now = timezone.now()
    sports = Snippet.objects.create(review_status=ReviewStatus.PUBLISHED, published_at=now, tags=["sports"])
    housing = Snippet.objects.create(review_status=ReviewStatus.PUBLISHED, published_at=now, tags=["housing"])
    fan = django_user_model.objects.create_user(email="fan@example.com")
    fan.profile.interests.set([interests["sports"]])
    renter = django_user_model.objects.create_user(email="renter@example.com")
    renter.profile.interests.set([interests["housing"]])

    assert recommend.rank([housing, sports], fan)[0] == sports
    assert recommend.rank([sports, housing], renter)[0] == housing
