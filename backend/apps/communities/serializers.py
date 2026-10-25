from rest_framework import serializers

from .models import (
    CommunityContribution,
    CommunityGroup,
    ContextEntry,
    FeedbackPrompt,
    FeedbackResponse,
    GlossaryTerm,
    Post,
    PostFlag,
    SourceFeed,
)


class CommunityGroupSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True)
    is_member = serializers.SerializerMethodField()
    interests = serializers.SlugRelatedField(slug_field="slug", many=True, read_only=True)

    class Meta:
        model = CommunityGroup
        fields = ["id", "name", "slug", "kind", "description", "municipality", "bbox", "languages", "interests",
                  "audiences", "is_active", "member_count", "is_member"]

    def get_is_member(self, obj) -> bool:
        user = self.context["request"].user
        return user.is_authenticated and obj.memberships.filter(user=user).exists()


class RecommendedCommunitySerializer(CommunityGroupSerializer):
    """A community suggested for the reader, with why (from services.recommend_communities)."""

    reasons = serializers.ListField(child=serializers.CharField(), read_only=True)
    score = serializers.FloatField(read_only=True)

    class Meta(CommunityGroupSerializer.Meta):
        fields = CommunityGroupSerializer.Meta.fields + ["reasons", "score"]


class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()
    like_count = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    community_name = serializers.CharField(source="community.name", read_only=True)
    community_slug = serializers.CharField(source="community.slug", read_only=True)
    is_mine = serializers.SerializerMethodField()
    flag_count = serializers.IntegerField(source="flags.count", read_only=True)
    answered_by = serializers.SerializerMethodField()
    translation = serializers.SerializerMethodField()
    hot = serializers.SerializerMethodField()
    misleading_reports = serializers.SerializerMethodField()
    community_note = serializers.SerializerMethodField()
    notes_to_rate = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ["id", "community", "community_name", "community_slug", "author", "author_name", "is_mine", "kind",
                  "body", "language", "translation", "answered_by", "image", "parent", "reply_count", "like_count", "liked",
                  "share_count", "status", "flag_count", "moderation_note", "hot", "misleading_reports",
                  "community_note", "notes_to_rate", "image_status", "faces_blurred",
                  "created_at", "updated_at"]
        read_only_fields = ["community", "author", "status", "language", "share_count", "moderation_note",
                            "image_status", "faces_blurred", "created_at", "updated_at"]

    def to_representation(self, obj):
        data = super().to_representation(obj)
        # A photo is shown only after a moderator checked the face blurring. Until then only its
        # author (and moderators) see it.
        if obj.image and obj.image_status != "approved":
            from . import services

            request = self.context.get("request")
            user = getattr(request, "user", None)
            if not (user and user.is_authenticated and (obj.author_id == user.pk or services.can_moderate(user, obj.community))):
                data["image"] = None
        if data.get("image") and self.context.get("request"):
            from .photos import signed_url

            data["image"] = signed_url(self.context["request"], obj)
        return data

    def _reader_chain(self):
        from apps.feed.services import language_chain, requester_language

        request = self.context.get("request")
        return language_chain(requester_language(request)) if request else ["fi", "en"]

    def get_answered_by(self, obj):
        """The published newsroom story that answers this question, in the reader's language."""
        from apps.common.choices import ReviewStatus
        from apps.feed.services import pick_version

        snippet = getattr(getattr(obj, "question", None), "linked_snippet", None)
        if not snippet or snippet.review_status != ReviewStatus.PUBLISHED:
            return None
        version = pick_version(snippet.versions.all(), self._reader_chain())
        return {"snippet": snippet.pk, "headline": version.headline if version else ""}

    def get_translation(self, obj):
        """Machine translation into the reader's language, if there is one (labelled in the app)."""
        want = self._reader_chain()[0]
        if not want or want == obj.language:
            return None
        t = next((t for t in obj.translations.all() if t.language == want), None)
        return {"language": t.language, "text": t.text, "from_language": obj.language} if t else None

    # Counts come annotated by the views (services.with_engagement); computed per post otherwise.
    def get_reply_count(self, obj) -> int:
        n = getattr(obj, "n_replies", None)
        return n if n is not None else obj.replies.filter(status=Post.Status.VISIBLE).count()

    def get_like_count(self, obj) -> int:
        n = getattr(obj, "n_likes", None)
        return n if n is not None else obj.likes.count()

    def get_liked(self, obj) -> bool:
        if hasattr(obj, "is_liked"):
            return obj.is_liked
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated and obj.likes.filter(user=request.user).exists())

    # --- Community Notes ---------------------------------------------------------------

    def get_hot(self, obj) -> bool:
        from . import services

        return services.is_hot(obj, self.get_like_count(obj), self.get_reply_count(obj))

    def get_misleading_reports(self, obj) -> int:
        from . import services

        return sum(1 for f in obj.flags.all() if f.reason in services.CONTEXT_REASONS)

    def _notes(self, obj):
        return list(obj.community_notes.all())

    def get_community_note(self, obj):
        """The note readers rated helpful, shown under the post ("Readers added context")."""
        from apps.notes.serializers import CommunityNoteSerializer

        shown = [n for n in self._notes(obj) if n.status == "helpful"]
        return CommunityNoteSerializer(shown[0], context=self.context).data if shown else None

    def get_notes_to_rate(self, obj) -> int:
        """Proposed notes this reader could rate (not theirs, not rated yet)."""
        request = self.context.get("request")
        uid = request.user.pk if request and request.user.is_authenticated else None
        return sum(1 for n in self._notes(obj) if n.status == "needs_more_ratings" and n.author_id != uid
                   and not any(r.rater_id == uid for r in n.ratings.all()))

    def get_is_mine(self, obj) -> bool:
        request = self.context.get("request")
        return bool(request and obj.author_id == request.user.id)

    def get_author_name(self, obj) -> str:
        return obj.author.username

    def validate(self, attrs):
        parent = attrs.get("parent")
        community = self.context.get("community")
        if parent and community and parent.community_id != community.id:
            raise serializers.ValidationError({"parent": "Parent post belongs to another community."})
        return attrs


class CommunityContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityContribution
        fields = ["id", "community", "kind", "body", "status", "contributor_consent", "named_persons_consent",
                  "occurrence_count", "is_story_candidate", "linked_snippet", "created_at"]
        read_only_fields = ["status", "occurrence_count", "is_story_candidate", "linked_snippet", "created_at"]


class SourceFeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = SourceFeed
        fields = ["id", "community", "name", "url", "kind", "is_active", "last_fetched_at"]
        read_only_fields = ["last_fetched_at"]


class GlossaryTermSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlossaryTerm
        fields = ["id", "community", "language", "term_fi", "term", "note"]


class ContextEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ContextEntry
        fields = ["id", "community", "language", "topic", "body", "valid_from", "reviewed_at", "reviewed_by"]
        read_only_fields = ["reviewed_by"]


class FeedbackPromptSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackPrompt
        fields = ["id", "community", "language", "question", "is_active"]


class FeedbackResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeedbackResponse
        fields = ["id", "prompt", "snippet", "useful", "missing", "rating", "created_at"]
        read_only_fields = ["created_at"]
        extra_kwargs = {"rating": {"min_value": 1, "max_value": 5}}

    def validate(self, attrs):
        if not attrs.get("useful") and not attrs.get("missing") and attrs.get("rating") is None:
            raise serializers.ValidationError("Provide at least one of useful, missing or rating.")
        return attrs


class FlagPostSerializer(serializers.Serializer):
    reason = serializers.ChoiceField(choices=PostFlag.Reason.choices, default=PostFlag.Reason.OTHER)
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class ModeratePostSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["keep", "remove"])
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class ModerationPostSerializer(PostSerializer):
    """A post as moderators see it: who reported it and why, and any earlier decision."""

    reports = serializers.SerializerMethodField()
    moderated_by_name = serializers.CharField(source="moderated_by", read_only=True, default=None)

    class Meta(PostSerializer.Meta):
        fields = PostSerializer.Meta.fields + ["reports", "moderated_by_name", "moderated_at"]

    def get_reports(self, post) -> list[dict]:
        return [
            {"reason": f.get_reason_display(), "note": f.note, "by": str(f.user), "at": f.created_at}
            for f in post.flags.all()
        ]
