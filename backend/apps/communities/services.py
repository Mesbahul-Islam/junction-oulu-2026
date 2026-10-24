"""Community business logic (no HTTP). FR-1.2, FR-3.10, FR-3.12."""

import re
import unicodedata

from django.db import transaction
from django.db.models import F

from .models import CommunityContribution, CommunityGroup, Membership, Post, PostFlag

# Questions asked this many times become story candidates for editors (FR-3.12).
RECURRING_QUESTION_THRESHOLD = 3

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def is_member(user, community) -> bool:
    if not user or not user.is_authenticated:
        return False
    return Membership.objects.filter(user=user, community=community).exists()


def join_community(user, community: CommunityGroup, role: str = Membership.Role.MEMBER) -> Membership:
    membership, _ = Membership.objects.get_or_create(user=user, community=community, defaults={"role": role})
    return membership


def leave_community(user, community: CommunityGroup) -> None:
    Membership.objects.filter(user=user, community=community).delete()


def normalize_text(text: str) -> str:
    """Lowercase, strip accents-insensitive punctuation and collapse whitespace (near-dup key).

    TODO: replace with embedding similarity once feed embeddings are available.
    """
    text = unicodedata.normalize("NFKC", text).casefold()
    text = _PUNCT_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()[:500]


@transaction.atomic
def record_question(*, community, author, body, contributor_consent=False, named_persons_consent=False):
    """FR-3.12: store a reader question, merging near-duplicates.

    If an open question with the same normalized text exists in the community, its
    occurrence_count is incremented instead of creating a new row; once it reaches
    RECURRING_QUESTION_THRESHOLD it is flagged as a story candidate. Never auto-published.
    Returns (contribution, created).
    """
    key = normalize_text(body)
    existing = (
        CommunityContribution.objects.select_for_update()
        .filter(
            community=community,
            kind=CommunityContribution.Kind.QUESTION,
            normalized_body=key,
            status__in=[CommunityContribution.Status.NEW, CommunityContribution.Status.IN_REVIEW],
        )
        .first()
    )
    if existing:
        CommunityContribution.objects.filter(pk=existing.pk).update(occurrence_count=F("occurrence_count") + 1)
        existing.refresh_from_db()
        if existing.occurrence_count >= RECURRING_QUESTION_THRESHOLD and not existing.is_story_candidate:
            existing.is_story_candidate = True
            existing.save(update_fields=["is_story_candidate", "updated_at"])
            # TODO: notify editorial / agents (community_signal trigger, FR-3.12).
        return existing, False

    contribution = CommunityContribution.objects.create(
        community=community,
        author=author,
        kind=CommunityContribution.Kind.QUESTION,
        body=body,
        normalized_body=key,
        contributor_consent=contributor_consent,
        named_persons_consent=named_persons_consent,
    )
    return contribution, True


def submit_contribution(*, community, author, kind, body, contributor_consent=False, named_persons_consent=False):
    """FR-3.10/3.12 entry point. Questions are de-duplicated; everything starts as status=new."""
    if kind == CommunityContribution.Kind.QUESTION:
        return record_question(
            community=community,
            author=author,
            body=body,
            contributor_consent=contributor_consent,
            named_persons_consent=named_persons_consent,
        )
    contribution = CommunityContribution.objects.create(
        community=community,
        author=author,
        kind=kind,
        body=body,
        normalized_body=normalize_text(body),
        contributor_consent=contributor_consent,
        named_persons_consent=named_persons_consent,
    )
    return contribution, True


# --- Community posts: moderation (JSN annex: content published by the public) ---------------

MODERATOR_ROLES = ("community_editor", "editor")


def can_moderate(user, community) -> bool:
    """Community editors of this community, editors and admins moderate its posts."""
    from apps.common.permissions import has_role

    return any(has_role(user, role, community=community.pk) for role in MODERATOR_ROLES)


def visible_posts(user, community_ids):
    """Top-level posts a member may see: never removed ones; hidden (flagged) ones only to their author."""
    from django.db.models import Q

    return (
        Post.objects.filter(community_id__in=community_ids, parent__isnull=True)
        .exclude(status=Post.Status.REMOVED)
        .filter(Q(status=Post.Status.VISIBLE) | Q(author=user))
        .select_related("author", "community")
    )


def flag_post(post, user, reason="other", note="") -> bool:
    """Record a flag; the post is hidden until a moderator decides. Returns True if newly flagged."""
    _, created = PostFlag.objects.get_or_create(post=post, user=user, defaults={"reason": reason, "note": note})
    if post.status == Post.Status.VISIBLE:
        post.status = Post.Status.HIDDEN
        post.save(update_fields=["status", "updated_at"])
    return created


def moderate_post(post, user, decision: str, note: str = "") -> Post:
    """keep → visible again (flags cleared); remove → removed for everyone."""
    from django.utils import timezone

    if decision not in ("keep", "remove"):
        raise ValueError("decision must be 'keep' or 'remove'")
    post.status = Post.Status.VISIBLE if decision == "keep" else Post.Status.REMOVED
    post.moderated_by, post.moderated_at, post.moderation_note = user, timezone.now(), note
    post.save(update_fields=["status", "moderated_by", "moderated_at", "moderation_note", "updated_at"])
    if decision == "keep":
        post.flags.all().delete()
    return post


# --- Community News: answers from the newsroom, translations --------------------------------

def is_question(body: str) -> bool:
    return "?" in (body or "")


def register_post(post) -> None:
    """After a member posts: note its language, pass questions on to the newsroom (FR-3.10),
    and translate it in the background for the community's other language groups."""
    from django.db import transaction

    from apps.agents.graph.text import guess_language

    post.language = guess_language(post.body)
    fields = ["language", "updated_at"]
    if post.parent_id is None and is_question(post.body):
        with transaction.atomic():
            post.question, _ = record_question(community=post.community, author=post.author, body=post.body)
        fields.append("question")
    post.save(update_fields=fields)

    from .tasks import translate_post

    transaction.on_commit(lambda: translate_post.delay(post.pk))


def post_translation_targets(post) -> list[str]:
    """The community's languages plus its members' profile languages, minus the post's own."""
    from apps.common.choices import SAMI_LANGUAGES

    from django.contrib.auth import get_user_model

    members = get_user_model().objects.filter(memberships__community=post.community)
    langs = set(post.community.languages or []) | set(members.values_list("preferred_language", flat=True))
    # Sámi is never machine-written (FR-3.9), not even for community posts.
    return sorted(lang for lang in langs if lang and lang != post.language and lang not in SAMI_LANGUAGES)


def answer_post(post, snippet, user):
    """Link a question post to the newsroom story that answers it (editors / community editors)."""
    if post.question is None:
        post.question = CommunityContribution.objects.create(
            community=post.community, author=post.author, kind=CommunityContribution.Kind.QUESTION,
            body=post.body, normalized_body=normalize_text(post.body),
        )
        post.save(update_fields=["question", "updated_at"])
    question = post.question
    question.linked_snippet = snippet
    question.status = (
        CommunityContribution.Status.ANSWERED if snippet.published_at else CommunityContribution.Status.IN_REVIEW
    )
    question.save(update_fields=["linked_snippet", "status", "updated_at"])
    return question
