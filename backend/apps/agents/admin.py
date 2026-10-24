from django.contrib import admin

from .models import AgentRun, AgentStep, RunStory


class RunStoryInline(admin.TabularInline):
    model = RunStory
    extra = 0
    fields = ("rank", "title", "jev_score", "ranked_by", "stage", "snippet")
    readonly_fields = fields


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "community", "trigger", "status", "max_stories", "started_at", "finished_at")
    list_filter = ("status", "trigger")
    readonly_fields = ("created_at", "updated_at")
    inlines = [RunStoryInline]


@admin.register(AgentStep)
class AgentStepAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "agent", "story", "duration_ms", "created_at")
    list_filter = ("agent",)
    raw_id_fields = ("run", "story", "snippet")
