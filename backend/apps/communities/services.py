"""Community business logic (no HTTP). FR-1.2, FR-3.10, FR-3.12."""

import re
import unicodedata

from django.db import transaction
from django.db.models import Count, F

from .models import CommunityContribution, CommunityGroup, Membership, Post, PostFlag, PostLike

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


def newsroom_for(community: CommunityGroup) -> CommunityGroup:
    """Topic communities have no newsroom of their own: their questions and tips go to the
    geographic community of the same municipality (whose sources the agents read)."""
    if community.kind == CommunityGroup.Kind.TOPIC:
        geo = CommunityGroup.objects.filter(
            kind=CommunityGroup.Kind.GEO, municipality__iexact=community.municipality, is_active=True
        ).first()
        if geo:
            return geo
    return community


def recommend_communities(user, limit: int = 6) -> list[tuple[CommunityGroup, float, list[str]]]:
    """Communities the reader hasn't joined, ranked by how well they fit the profile:
    where they live, their situation (newcomer, student...), shared topics and language.
    Returns (community, score, reasons) for those that match at least one of these."""
    from apps.accounts.models import Interest
    from apps.agents.graph.text import LANGUAGE_LABELS
    from apps.common.choices import ReaderSituation

    profile = getattr(user, "profile", None)
    location = profile.location if profile else None
    my_interests = set(profile.interests.values_list("pk", flat=True)) if profile else set()
    names = dict(Interest.objects.filter(pk__in=my_interests).values_list("pk", "name"))
    situation = user.reader_situation
    language = user.preferred_language
    joined = set(user.memberships.values_list("community_id", flat=True))

    ranked = []
    groups = CommunityGroup.objects.filter(is_active=True).exclude(pk__in=joined).prefetch_related("interests")
    for group in groups.annotate(member_count=Count("memberships")):
        score, reasons = 0.0, []
        if group.kind == CommunityGroup.Kind.GEO:
            if location and _in_area(location, group):
                score += 3
                reasons.append(f"You live in {group.municipality or group.name}")
            elif not location:  # no location given: the platform's town community is still where they live
                score += 3
                reasons.append(f"Local news and neighbours in {group.municipality or group.name}")
        if group.audiences and situation in group.audiences:
            score += 2
            reasons.append(f"For {ReaderSituation(situation).label.lower()}s")
        shared = [names[i.pk] for i in group.interests.all() if i.pk in my_interests]
        if shared:
            score += 1.5 * len(shared)
            reasons.append("You follow " + ", ".join(shared[:3]))
        if score and language in group.languages and language not in ("fi", "en"):  # worth saying for smaller languages
            score += 0.5
            reasons.append(f"Members read {LANGUAGE_LABELS.get(language, language)}")
        if score:
            ranked.append((group, score + min(group.member_count, 50) / 100, reasons))
    ranked.sort(key=lambda r: -r[1])
    return ranked[:limit]


def _in_area(location, group: CommunityGroup) -> bool:
    if location.municipality and group.municipality and location.municipality.lower() == group.municipality.lower():
        return True
    if group.bbox and location.lat is not None and location.lng is not None:
        min_lng, min_lat, max_lng, max_lat = group.bbox
        return min_lng <= location.lng <= max_lng and min_lat <= location.lat <= max_lat
    return False


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
    community = newsroom_for(community)
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
    community = newsroom_for(community)
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


def with_engagement(qs, user):
    """Annotate posts with visible reply count, like count and whether `user` liked each."""
    from django.db.models import Exists, OuterRef, Q

    return qs.annotate(
        n_replies=Count("replies", filter=Q(replies__status=Post.Status.VISIBLE), distinct=True),
        n_likes=Count("likes", distinct=True),
        is_liked=Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user)),
    )


def set_like(post, user, liked: bool) -> int:
    """Like or unlike a post; returns its like count."""
    if liked:
        PostLike.objects.get_or_create(post=post, user=user)
    else:
        PostLike.objects.filter(post=post, user=user).delete()
    return post.likes.count()


def record_share(post) -> int:
    Post.objects.filter(pk=post.pk).update(share_count=F("share_count") + 1)
    post.refresh_from_db(fields=["share_count"])
    return post.share_count


# "False or misleading" is answered with context, not removal: the post stays up and members
# are asked to add a Community Note (like X). Hate, privacy, spam... hide it for a moderator.
CONTEXT_REASONS = {"false"}
# A post is "hot" when likes + 2 x replies + 2 x shares reach this within its first 3 days.
HOT_SCORE = 15
HOT_DAYS = 3


def is_hot(post, likes: int, replies: int) -> bool:
    from datetime import timedelta

    from django.utils import timezone

    fresh = post.created_at and timezone.now() - post.created_at < timedelta(days=HOT_DAYS)
    return bool(fresh and likes + 2 * replies + 2 * post.share_count >= HOT_SCORE)


def flag_post(post, user, reason="other", note="") -> bool:
    """Record a flag. A misleading report asks for context; other reasons hide the post until a
    moderator decides. Returns True if newly flagged."""
    _, created = PostFlag.objects.get_or_create(post=post, user=user, defaults={"reason": reason, "note": note})
    if reason in CONTEXT_REASONS:
        return created
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
