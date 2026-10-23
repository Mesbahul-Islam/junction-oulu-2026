from django.contrib import admin

from .models import Comment, Interaction, Snippet, SnippetReport, SnippetVersion, SourceDocument


class SnippetVersionInline(admin.StackedInline):
    model = SnippetVersion
    extra = 0
    raw_id_fields = ["approved_by"]


@admin.register(Snippet)
class SnippetAdmin(admin.ModelAdmin):
    list_display = ["id", "__str__", "community", "risk_tier", "review_status", "confidence", "published_at"]
    list_filter = ["review_status", "risk_tier", "community", "ai_generated", "arrival_day_bucket"]
    raw_id_fields = ["created_by_agent_run"]
    filter_horizontal = ["source_documents"]
    inlines = [SnippetVersionInline]


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "publisher", "version", "fetched_at"]
    search_fields = ["title", "url"]


@admin.register(SnippetVersion)
class SnippetVersionAdmin(admin.ModelAdmin):
    list_display = ["snippet", "language", "headline", "review_status", "is_machine_translated"]
    list_filter = ["language", "review_status", "is_machine_translated"]


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ["user", "snippet", "kind", "created_at"]
    list_filter = ["kind"]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ["user", "snippet", "parent", "created_at"]


@admin.register(SnippetReport)
class SnippetReportAdmin(admin.ModelAdmin):
    list_display = ["snippet", "reason", "user", "resolved", "created_at"]
    list_filter = ["reason", "resolved"]
