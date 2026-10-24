from rest_framework import serializers

from .models import RATING_TAGS, CommunityNote, NoteRating, validate_citation_urls


class CommunityNoteSerializer(serializers.ModelSerializer):
    """A note as members see it: anonymous (like X's Community Notes), in the reader's language
    when a translation exists, with whether they wrote or already rated it."""

    citation_urls = serializers.ListField(child=serializers.URLField(), min_length=1)
    rating_count = serializers.IntegerField(source="ratings.count", read_only=True)
    is_mine = serializers.SerializerMethodField()
    my_rating = serializers.SerializerMethodField()
    translation = serializers.SerializerMethodField()

    class Meta:
        model = CommunityNote
        fields = [
            "id", "snippet", "post", "claim_summary", "context", "citation_urls", "language", "translation",
            "status", "rating_count", "is_mine", "my_rating", "created_at",
        ]
        read_only_fields = ["id", "status", "language", "rating_count", "created_at"]

    def _user(self):
        request = self.context.get("request")
        return request.user if request and request.user.is_authenticated else None

    def get_is_mine(self, note) -> bool:
        user = self._user()
        return bool(user and note.author_id == user.pk)

    def get_my_rating(self, note) -> str | None:
        user = self._user()
        rating = next((r for r in note.ratings.all() if user and r.rater_id == user.pk), None)
        return rating.value if rating else None

    def get_translation(self, note):
        """{language, claim_summary, context, from_language} in the reader's language, if translated."""
        from apps.feed.services import language_chain, requester_language

        request = self.context.get("request")
        if not request or not note.translations:
            return None
        want = language_chain(requester_language(request))[0]
        t = note.translations.get(want)
        return {"language": want, **t, "from_language": note.language} if t and want != note.language else None

    def validate_citation_urls(self, value):
        validate_citation_urls(value)
        return value

    def validate(self, attrs):
        if bool(attrs.get("snippet")) == bool(attrs.get("post")):
            raise serializers.ValidationError("Attach the note to exactly one of snippet or post.")
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
