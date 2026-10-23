"""Smoke tests of pure feed logic (no DB)."""

from apps.feed import recommend as r
from apps.feed import services as s


def test_language_chain_fallback():
    assert s.language_chain("ar") == ["ar", "fi", "en"]
    assert s.language_chain("fi") == ["fi", "en"]


def test_pick_version_skips_unapproved():
    class V:
        def __init__(self, language, review_status):
            self.language, self.review_status = language, review_status

    versions = [V("ar", "pending_review"), V("fi", "approved"), V("en", "approved")]
    assert s.pick_version(versions, ["ar", "fi", "en"]).language == "fi"
    assert s.pick_version([V("ar", "draft")], ["ar"]) is None


def test_arrival_buckets():
    assert s.arrival_bucket_for(0) == "first_48h"
    assert s.arrival_bucket_for(3) == "first_week"
    assert s.arrival_bucket_for(20) == "first_month"
    assert s.arrival_bucket_for(45) is None
    assert s.arrival_buckets_to_show("first_month") == ["first_month", "first_week", "first_48h"]


def test_interest_overlap_and_geo():
    assert r.interest_overlap(["housing", "kela"], {"housing": 1.0}) == 0.5
    assert r.interest_overlap([], {"x": 1}) == 0.0
    ctx = r.UserContext(community_ids={7}, point=(25.47, 65.01))
    assert r.geo_relevance(7, [None], ctx) == r.MEMBER_GEO_SCORE
    assert r.geo_relevance(8, [[25.0, 64.8, 26.0, 65.2]], ctx) == r.BBOX_GEO_SCORE
    assert r.geo_relevance(8, [[20.0, 60.0, 21.0, 61.0]], ctx) == 0.0


def test_engagement_and_decay():
    assert r.engagement_signal(r.EngagementStats()) == 0.0
    hot = r.engagement_signal(r.EngagementStats(views=10, read_throughs=8, expands=50, likes=100))
    assert 0.89 < hot <= 1.0
    assert r.time_decay(0) == 1.0
    assert abs(r.time_decay(48) - 0.5) < 1e-9


def test_comment_tree():
    class C:
        def __init__(self, pk, parent_id):
            self.pk, self.parent_id, self.user, self.body, self.created_at = pk, parent_id, "u", "b", None

    tree = s.build_comment_tree([C(1, None), C(2, 1), C(3, None), C(4, 2)])
    assert [n["id"] for n in tree] == [1, 3]
    assert tree[0]["replies"][0]["replies"][0]["id"] == 4
