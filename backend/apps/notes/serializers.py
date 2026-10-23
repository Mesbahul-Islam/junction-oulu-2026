from rest_framework import serializers

from .models import RATING_TAGS, CommunityNote, NoteRating, validate_citation_urls


class CommunityNoteSerializer(serializers.ModelSerializer):
    citation_urls = serializers.ListField(child=serializers.URLField(), min_length=1)
    rating_count = serializers.IntegerField(source="ratings.count", read_only=True)

    class Meta:
        model = CommunityNote
        fields = [
            "id", "snippet", "post", "claim_summary", "context", "citation_urls",
            "status", "rating_count", "created_at",
        ]
        read_only_fields = ["id", "status", "rating_count", "created_at"]

    def validate_citation_urls(self, value):
        validate_citation_urls(value)
        return value

    def validate(self, attrs):
        if bool(attrs.get("snippet")) == bool(attrs.get("post")):
            raise serializers.ValidationError("Attach the note to exactly one of snippet or post.")
        # TODO: for posts, require the author to be a member of post.community (posts are members-only).
        return attrs


class PublicNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CommunityNote
        fields = ["id", "snippet", "post", "claim_summary", "context", "citation_urls", "created_at"]


class NoteRatingSerializer(serializers.ModelSerializer):
    tags = serializers.ListField(child=serializers.ChoiceField(choices=RATING_TAGS), min_length=1)

    class Meta:
        model = NoteRating
        fields = ["id", "value", "tags", "created_at"]
        read_only_fields = ["id", "created_at"]
