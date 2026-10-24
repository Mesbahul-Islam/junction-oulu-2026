from rest_framework import serializers

from apps.feed.models import SnippetVersion

from .models import STANDARDS_CHECKLIST, AuditLogEntry, ChecklistItem, Correction, ReviewTask, StandardsCheck, VerificationResult


class VersionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = SnippetVersion
        fields = ["language", "headline", "summary", "key_facts", "review_status", "is_machine_translated"]


class ReviewTaskSerializer(serializers.ModelSerializer):
    risk_tier = serializers.CharField(source="snippet.risk_tier", read_only=True)
    confidence = serializers.FloatField(source="snippet.confidence", read_only=True)
    community = serializers.CharField(source="snippet.community.slug", read_only=True, default=None)
    versions = serializers.SerializerMethodField()
    flags = serializers.SerializerMethodField()
    # The AI newsroom's verdict: "ready" (one click to publish) or "needs_review", with reasons.
    review_level = serializers.CharField(source="snippet.review_level", read_only=True)
    review_reasons = serializers.JSONField(source="snippet.review_reasons", read_only=True)

    class Meta:
        model = ReviewTask
        fields = [
            "id", "snippet", "language", "required_role", "priority", "reason", "status",
            "risk_tier", "confidence", "community", "assigned_to", "decided_by", "decided_at",
            "comment", "created_at", "versions", "flags", "review_level", "review_reasons",
        ]
        read_only_fields = fields

    def get_flags(self, task):
        """What the agents flagged, so the reviewer decides with the evidence in front of them."""
        snippet = task.snippet
        latest = {}
        for v in VerificationResult.objects.filter(snippet=snippet).order_by("created_at"):
            if task.language in (None, v.language):
                latest[v.language] = v
        verification = [
            {
                "language": lang, "passed": v.passed, "confidence": round(v.confidence, 2),
                "issues": [
                    {k: m.get(k) for k in ("kind", "value", "issue", "severity")} for m in v.mismatches
                ],
            }
            for lang, v in sorted(latest.items())
        ]
        std = StandardsCheck.objects.filter(snippet=snippet).order_by("-created_at").first()
        labels = dict(STANDARDS_CHECKLIST)
        standards = None
        if std:
            standards = {
                "passed": std.passed,
                "failed": [{"key": k, "label": labels.get(k, k)} for k, r in std.results.items() if r == "fail"],
                "notes": [{"key": k, "label": labels.get(k, k), "note": r} for k, r in std.results.items() if str(r).startswith("note")],
            }
        checklist = [
            {
                "key": c.key, "label": c.label, "clauses": c.clauses, "confirmed": c.confirmed_at is not None,
                "confirmed_by": str(c.confirmed_by) if c.confirmed_by else None, "note": c.note,
            }
            for c in ChecklistItem.objects.filter(snippet=snippet)
        ] if task.language is None else []
        sources = [{"title": d.title, "url": d.url, "publisher": d.publisher} for d in snippet.source_documents.all()]
        return {"verification": verification, "standards": standards, "checklist": checklist, "sources": sources}

    def get_versions(self, task):
        qs = task.snippet.versions.all()
        if task.language:
            qs = qs.filter(language=task.language)
        return VersionBriefSerializer(qs, many=True).data


class ApproveSerializer(serializers.Serializer):
    edits = serializers.DictField(required=False)
    # Sensitive-topic checklist keys the editor confirms with this approval (required for the
    # whole-story task when the snippet has open checklist items), plus optional notes per key.
    confirm = serializers.ListField(child=serializers.CharField(), required=False)
    notes = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)


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
