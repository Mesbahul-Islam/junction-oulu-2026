"""Smoke tests of the pure note-status rule (FR-4) — no DB."""

import pytest
from django.core.exceptions import ValidationError

from apps.notes.models import validate_citation_urls, validate_rating_tags
from apps.notes.services import status_from_ratings


def test_needs_more_ratings_below_minimum():
    assert status_from_ratings([("helpful", 1)] * 4) == "needs_more_ratings"


def test_helpful_requires_two_perspectives():
    same_group = [("helpful", 1)] * 5
    assert status_from_ratings(same_group) == "needs_more_ratings"
    bridged = [("helpful", 1)] * 3 + [("helpful", 2), ("somewhat_helpful", 2)]
    assert status_from_ratings(bridged) == "helpful"


def test_unaffiliated_raters_do_not_bridge():
    assert status_from_ratings([("helpful", 1)] * 4 + [("helpful", None)]) == "needs_more_ratings"


def test_not_helpful():
    assert status_from_ratings([("not_helpful", 1)] * 4 + [("somewhat_helpful", 2)]) == "not_helpful"


def test_validators():
    validate_citation_urls(["https://migri.fi/en/home"])
    with pytest.raises(ValidationError):
        validate_citation_urls([])
    with pytest.raises(ValidationError):
        validate_citation_urls(["not a url"])
    validate_rating_tags(["clear_sources"])
    with pytest.raises(ValidationError):
        validate_rating_tags(["made_up"])
