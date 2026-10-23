from django.contrib import admin

from .models import AgentRun, AgentStep


class AgentStepInline(admin.TabularInline):
    model = AgentStep
    extra = 0
    fields = ("agent", "duration_ms", "snippet", "created_at")
    readonly_fields = fields
    show_change_link = True


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("id", "community", "trigger", "status", "started_at", "finished_at")
    list_filter = ("status", "trigger", "community")
    readonly_fields = ("created_at", "updated_at")
    inlines = [AgentStepInline]


@admin.register(AgentStep)
class AgentStepAdmin(admin.ModelAdmin):
    list_display = ("id", "run", "agent", "duration_ms", "snippet", "created_at")
    list_filter = ("agent",)
    raw_id_fields = ("run", "snippet")
