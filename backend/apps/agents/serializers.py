from rest_framework import serializers

from .models import AgentRun, AgentStep


class AgentStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentStep
        fields = ["id", "agent", "input", "output", "snippet", "duration_ms", "created_at"]
        read_only_fields = fields


class AgentRunSerializer(serializers.ModelSerializer):
    snippet_ids = serializers.SerializerMethodField()

    class Meta:
        model = AgentRun
        fields = ["id", "community", "trigger", "status", "started_at", "finished_at", "error", "snippet_ids", "created_at"]
        read_only_fields = fields

    def get_snippet_ids(self, obj):
        from django.apps import apps

        Snippet = apps.get_model("feed", "Snippet")
        return list(Snippet.objects.filter(created_by_agent_run=obj).values_list("pk", flat=True))


class AgentRunDetailSerializer(AgentRunSerializer):
    steps = AgentStepSerializer(many=True, read_only=True)

    class Meta(AgentRunSerializer.Meta):
        fields = AgentRunSerializer.Meta.fields + ["state", "steps"]
        read_only_fields = fields


class AgentRunCreateSerializer(serializers.Serializer):
    community = serializers.IntegerField()
    source_ids = serializers.ListField(child=serializers.IntegerField(), required=False, allow_empty=True)
    language_targets = serializers.ListField(child=serializers.CharField(), required=False)
    max_items = serializers.IntegerField(required=False, min_value=1, max_value=50)

    def validate_community(self, value):
        from django.apps import apps

        if not apps.get_model("communities", "CommunityGroup").objects.filter(pk=value).exists():
            raise serializers.ValidationError("Unknown community.")
        return value
