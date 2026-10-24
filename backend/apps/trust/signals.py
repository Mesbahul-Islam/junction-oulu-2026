"""Recompute a member's trust when something that counts changes. Read-only towards other apps:
these receivers only update MemberTrust, never the post, note or contribution."""

import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _refresh(user, community):
    if user is None or community is None:
        return
    from .services import refresh

    try:
        refresh(user, community)
    except Exception:  # never let scoring break the action the member took
        logger.exception("Trust refresh failed for %s in %s", user, community)


def _note_community(note):
    return note.snippet.community if note.snippet_id else (note.post.community if note.post_id else None)


@receiver([post_save, post_delete], sender="communities.PostLike")
def like_changed(sender, instance, **kwargs):
    post = instance.post
    _refresh(post.author, post.community)


@receiver(post_save, sender="communities.Post")
def post_changed(sender, instance, **kwargs):
    if instance.status == "removed" or kwargs.get("update_fields") is None:
        _refresh(instance.author, instance.community)


@receiver(post_save, sender="communities.CommunityContribution")
def contribution_changed(sender, instance, **kwargs):
    _refresh(instance.author, instance.community)


@receiver(post_save, sender="notes.CommunityNote")
def note_changed(sender, instance, **kwargs):
    community = _note_community(instance)
    _refresh(instance.author, community)
    # A note's verdict also decides whose ratings were right.
    if instance.status in ("helpful", "not_helpful"):
        for rater in {r.rater for r in instance.ratings.select_related("rater")}:
            _refresh(rater, community)
