"""Community News: member posts, flagging and moderation (JSN annex, content published by the public)."""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.communities.models import CommunityGroup, Membership, Post


@pytest.fixture
def oulu(db):
    return CommunityGroup.objects.create(name="Oulu", slug="oulu")


def member(django_user_model, community, email, role=None):
    user = django_user_model.objects.create_user(email=email, password="x")
    Membership.objects.create(user=user, community=community)
    if role:
        UserRole.objects.create(user=user, role=role, community=community)
    client = APIClient()
    client.force_authenticate(user)
    return user, client


def test_flag_hides_post_until_moderator_decides(django_user_model, oulu):
    author, author_c = member(django_user_model, oulu, "a@x.fi")
    _, reader_c = member(django_user_model, oulu, "r@x.fi")
    _, mod_c = member(django_user_model, oulu, "m@x.fi", role="community_editor")
    post = author_c.post("/api/communities/groups/oulu/posts/", {"body": "Free bikes at the station!"}, format="json").data

    assert [p["id"] for p in reader_c.get("/api/communities/news/").data["results"]] == [post["id"]]
    resp = reader_c.post(f"/api/communities/groups/oulu/posts/{post['id']}/flag/", {"reason": "spam"}, format="json")
    assert resp.status_code == 200 and "hidden" in resp.data["detail"]

    assert reader_c.get("/api/communities/news/").data["results"] == []  # hidden from others
    own = author_c.get("/api/communities/news/").data["results"]
    assert own[0]["status"] == "hidden" and own[0]["is_mine"]  # the author still sees it, with a notice

    queue = mod_c.get("/api/communities/moderation/").data["results"]
    assert [p["id"] for p in queue] == [post["id"]] and queue[0]["flag_count"] == 1
    assert reader_c.get("/api/communities/moderation/").data["results"] == []  # not a moderator

    assert reader_c.post(f"/api/communities/moderation/{post['id']}/decide/", {"decision": "remove"}, format="json").status_code == 403
    mod_c.post(f"/api/communities/moderation/{post['id']}/decide/", {"decision": "remove", "note": "spam"}, format="json")
    assert Post.objects.get(pk=post["id"]).status == "removed"
    assert author_c.get("/api/communities/news/").data["results"] == []  # removed for everyone


def test_keep_restores_and_clears_flags(django_user_model, oulu):
    author, author_c = member(django_user_model, oulu, "a@x.fi")
    _, reader_c = member(django_user_model, oulu, "r@x.fi")
    _, mod_c = member(django_user_model, oulu, "m@x.fi", role="community_editor")
    post = author_c.post("/api/communities/groups/oulu/posts/", {"body": "Library opens at 10"}, format="json").data
    reader_c.post(f"/api/communities/groups/oulu/posts/{post['id']}/flag/", {"reason": "other"}, format="json")
    mod_c.post(f"/api/communities/moderation/{post['id']}/decide/", {"decision": "keep"}, format="json")
    p = Post.objects.get(pk=post["id"])
    assert p.status == "visible" and p.flags.count() == 0 and p.moderated_at


def test_only_moderators_post_announcements(django_user_model, oulu):
    _, member_c = member(django_user_model, oulu, "a@x.fi")
    _, mod_c = member(django_user_model, oulu, "m@x.fi", role="community_editor")
    assert member_c.post("/api/communities/groups/oulu/posts/", {"body": "x", "kind": "announcement"}, format="json").data["kind"] == "post"
    assert mod_c.post("/api/communities/groups/oulu/posts/", {"body": "x", "kind": "announcement"}, format="json").data["kind"] == "announcement"


def test_community_news_only_shows_my_communities(django_user_model, oulu):
    other = CommunityGroup.objects.create(name="Kemi", slug="kemi")
    _, a_c = member(django_user_model, oulu, "a@x.fi")
    _, b_c = member(django_user_model, other, "b@x.fi")
    b_c.post("/api/communities/groups/kemi/posts/", {"body": "Kemi only"}, format="json")
    assert a_c.get("/api/communities/news/").data["results"] == []


def test_moderation_history_views(django_user_model, oulu):
    author, author_c = member(django_user_model, oulu, "a@x.fi")
    _, reader_c = member(django_user_model, oulu, "r@x.fi")
    _, mod_c = member(django_user_model, oulu, "m@x.fi", role="community_editor")
    ids = [author_c.post("/api/communities/groups/oulu/posts/", {"body": b}, format="json").data["id"] for b in ("one", "two")]
    for i in ids:
        reader_c.post(f"/api/communities/groups/oulu/posts/{i}/flag/", {"reason": "spam", "note": "ad"}, format="json")
    pending = mod_c.get("/api/communities/moderation/").data["results"]
    assert pending[0]["reports"][0]["reason"] == "Spam or advertising" and pending[0]["reports"][0]["note"] == "ad"
    mod_c.post(f"/api/communities/moderation/{ids[0]}/decide/", {"decision": "remove", "note": "spam"}, format="json")
    mod_c.post(f"/api/communities/moderation/{ids[1]}/decide/", {"decision": "keep"}, format="json")
    removed = mod_c.get("/api/communities/moderation/?status=removed").data["results"]
    kept = mod_c.get("/api/communities/moderation/?status=kept").data["results"]
    assert [p["id"] for p in removed] == [ids[0]] and removed[0]["moderated_by_name"]
    assert [p["id"] for p in kept] == [ids[1]]
