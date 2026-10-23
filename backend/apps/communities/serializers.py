from rest_framework import serializers

from .models import (
    CommunityContribution,
    CommunityGroup,
    ContextEntry,
    FeedbackPrompt,
    FeedbackResponse,
    GlossaryTerm,
    Post,
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

    class Meta:
        model = Post
        fields = ["id", "community", "author", "author_name", "kind", "body", "image", "parent",
                  "reply_count", "created_at", "updated_at"]
        read_only_fields = ["community", "author", "created_at", "updated_at"]

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
