from rest_framework import serializers

from .models import MemberTrust
from .services import next_step


class MemberTrustSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    community_slug = serializers.CharField(source="community.slug", read_only=True)
    community_name = serializers.CharField(source="community.name", read_only=True)
    approved_by = serializers.CharField(source="approved_by.username", read_only=True, default=None)
    next = serializers.SerializerMethodField()

    class Meta:
        model = MemberTrust
        fields = ["id", "user", "username", "community", "community_slug", "community_name", "score", "verified",
                  "breakdown", "level", "approved_by", "approved_at", "next"]

    def get_next(self, obj):
        return next_step(obj)


class VoiceSerializer(serializers.ModelSerializer):
    """Public view of a trusted voice: no score breakdown."""

    username = serializers.CharField(source="user.username", read_only=True)
    community_slug = serializers.CharField(source="community.slug", read_only=True)

    class Meta:
        model = MemberTrust
        fields = ["user", "username", "community_slug", "approved_at"]
