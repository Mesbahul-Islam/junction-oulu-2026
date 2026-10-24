"""Feed card payload (FR-2.1, FR-3.13 disclosure, FR-4 public notes).

The risk tier is an internal editorial label (how much review a snippet needs) and is
deliberately not part of the reader-facing card; editors see it in the review queue.
"""

from rest_framework import serializers

from . import services
from .models import Comment, SnippetReport


def _display(user):
    if user is None:
        return None
    return getattr(user, "display_name", "") or user.get_full_name() or "Editor"


def _for_you(situation, version, original) -> dict:
    for v in (version, original):
        text = (v.explainer or {}).get(situation) if v and situation else None
        if text:
            return {"for_you": text, "for_you_language": v.language}
    return {"for_you": None, "for_you_language": None}


class SnippetCardSerializer(serializers.Serializer):
    """Read-only card. Context: `request`, `language_chain`. Expects services.published_snippets() qs."""

    def to_representation(self, snippet):
        chain = self.context.get("language_chain") or services.FALLBACK_LANGUAGES
        version = services.pick_version(snippet.versions.all(), chain)
        original = services.pick_version(snippet.versions.all(), [services.Language.FINNISH])
        user = self.context.get("reader") or getattr(self.context.get("request"), "user", None)
        situation = user.reader_situation if user is not None and user.is_authenticated else None
        request = self.context.get("request")
        image_url = None
        if snippet.image:  # a picture uploaded by an editor wins
            image_url = request.build_absolute_uri(snippet.image.url) if request else snippet.image.url
        else:  # else the lead picture of the source article (already an absolute URL)
            image_url = next((d.image_url for d in snippet.source_documents.all() if d.image_url), None)
        reviewer = _display(version.approved_by) if version else None
        corrections = sorted(snippet.corrections.all(), key=lambda c: c.created_at, reverse=True)
        latest = next((c for c in corrections if c.published_at), None)
        explainer = version.explainer if version else {}
        return {
            "id": snippet.pk,
            # FR-3.9: shown in the reader's profile language when that version is approved.
            "language": version.language if version else None,
            "requested_language": chain[0],
            "in_your_language": bool(version and version.language == chain[0]),
            "headline": version.headline if version else "",
            "summary": version.summary if version else "",
            "key_facts": version.key_facts if version else [],
            "explainer": explainer,
            # "What this means for me" for this reader's situation (newcomer, student ...);
            # if the translation lacks it, the original's text (for_you_language says which).
            **_for_you(situation, version, original),
            "situation": situation,
            "background": version.background if version else "",
            "image_url": image_url,
            "source_urls": [d.url for d in snippet.source_documents.all()],
            "author": reviewer or "Newsroom",
            "community": snippet.community.slug if snippet.community_id else None,
            "tags": snippet.tags,
            "reader_needs": snippet.reader_needs,
            "published_at": snippet.published_at,
            "verified_at": snippet.verified_at,
            "review_status": snippet.review_status,
            "metrics": {
                "likes": getattr(snippet, "n_likes", 0),
                "shares": getattr(snippet, "n_shares", 0),
                "bookmarks": getattr(snippet, "n_bookmarks", 0),
                "comments": getattr(snippet, "n_comments", 0),
            },
            "ai_disclosure": {
                "ai_generated": snippet.ai_generated,
                "roles": services.agent_roles(snippet) if snippet.ai_generated else [],
                "reviewer": reviewer,
                "verified_at": snippet.verified_at,
                "machine_translated": bool(version and version.is_machine_translated),
            },
            "correction_note": latest.what_changed if latest else None,
            # The Finnish original, always alongside a translation so readers can compare.
            "original": None if not original or (version and version.pk == original.pk) else {
                "language": original.language,
                "headline": original.headline,
                "summary": original.summary,
                "key_facts": original.key_facts,
            },
            # This reader's own state, for filled heart / bookmark icons.
            "liked": "like" in self.context.get("mine", {}).get(snippet.pk, ()),
            "bookmarked": "bookmark" in self.context.get("mine", {}).get(snippet.pk, ()),
            # "Why am I seeing this?": set by recommend.rank() on feed lists only.
            "ranking": getattr(snippet, "ranking", None),
            "community_notes": [
                {"id": n.pk, "claim_summary": n.claim_summary, "context": n.context, "citation_urls": n.citation_urls}
                for n in snippet.community_notes.all()  # prefetched: status == helpful only
            ],
        }


class InteractSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=sorted(services.INTERACT_KINDS))


class CommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Comment
        fields = ["id", "parent", "body", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_parent(self, parent):
        snippet = self.context.get("snippet")
        if parent is not None and snippet is not None and parent.snippet_id != snippet.pk:
            raise serializers.ValidationError("Parent comment belongs to another snippet.")
        return parent


class SnippetReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SnippetReport
        fields = ["id", "reason", "body", "resolved", "created_at"]
        read_only_fields = ["id", "resolved", "created_at"]
