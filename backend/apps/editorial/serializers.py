from rest_framework import serializers

from apps.feed.models import SnippetVersion

from .models import AuditLogEntry, Correction, ReviewTask


class VersionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = SnippetVersion
        fields = ["language", "headline", "summary", "key_facts", "review_status", "is_machine_translated"]


class ReviewTaskSerializer(serializers.ModelSerializer):
    risk_tier = serializers.CharField(source="snippet.risk_tier", read_only=True)
    confidence = serializers.FloatField(source="snippet.confidence", read_only=True)
    community = serializers.CharField(source="snippet.community.slug", read_only=True, default=None)
    versions = serializers.SerializerMethodField()

    class Meta:
        model = ReviewTask
        fields = [
            "id", "snippet", "language", "required_role", "priority", "reason", "status",
            "risk_tier", "confidence", "community", "assigned_to", "decided_by", "decided_at",
            "comment", "created_at", "versions",
        ]
        read_only_fields = fields

    def get_versions(self, task):
        qs = task.snippet.versions.all()
        if task.language:
            qs = qs.filter(language=task.language)
        return VersionBriefSerializer(qs, many=True).data


class ApproveSerializer(serializers.Serializer):
    edits = serializers.DictField(required=False)


class CommentInputSerializer(serializers.Serializer):
    comment = serializers.CharField()


class BatchApproveSerializer(serializers.Serializer):
    task_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=200)


class AuditLogEntrySerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = AuditLogEntry
        fields = ["id", "action", "actor", "agent", "payload", "created_at"]


class CorrectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Correction
        fields = ["id", "snippet", "language", "what_changed", "published_at"]
