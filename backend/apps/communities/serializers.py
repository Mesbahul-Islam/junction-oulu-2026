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

    class Meta:
        model = CommunityGroup
        fields = ["id", "name", "slug", "kind", "municipality", "bbox", "languages", "is_active",
                  "member_count", "is_member"]

    def get_is_member(self, obj) -> bool:
        user = self.context["request"].user
        return user.is_authenticated and obj.memberships.filter(user=user).exists()


class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()
    reply_count = serializers.IntegerField(source="replies.count", read_only=True)
    community_name = serializers.CharField(source="community.name", read_only=True)
    community_slug = serializers.CharField(source="community.slug", read_only=True)
    is_mine = serializers.SerializerMethodField()
    flag_count = serializers.IntegerField(source="flags.count", read_only=True)

    class Meta:
        model = Post
        fields = ["id", "community", "community_name", "community_slug", "author", "author_name", "is_mine", "kind",
                  "body", "image", "parent", "reply_count", "status", "flag_count", "moderation_note",
                  "created_at", "updated_at"]
        read_only_fields = ["community", "author", "status", "moderation_note", "created_at", "updated_at"]

    def get_is_mine(self, obj) -> bool:
        request = self.context.get("request")
        return bool(request and obj.author_id == request.user.id)

    def get_author_name(self, obj) -> str:
        return obj.author.display_name or obj.author.email.split("@")[0]

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
