"""Translations target the community's languages plus every member's profile language."""

import pytest

from apps.agents.graph.nodes.scout import _targets, load_audience_languages
from apps.communities.models import CommunityGroup, Membership


@pytest.mark.django_db
def test_member_profile_languages_become_targets(django_user_model):
    oulu = CommunityGroup.objects.create(name="Oulu", slug="oulu", languages=["fi", "en", "uk"])
    for email, lang in [("a@x.fi", "ru"), ("b@x.fi", "so"), ("c@x.fi", "fi")]:
        Membership.objects.create(user=django_user_model.objects.create_user(email=email, preferred_language=lang), community=oulu)

    audience = load_audience_languages(oulu)
    assert audience == ["fi", "ru", "so"]
    assert _targets({}, {"languages": oulu.languages}, audience) == ["en", "uk", "ru", "so"]  # source fi excluded
