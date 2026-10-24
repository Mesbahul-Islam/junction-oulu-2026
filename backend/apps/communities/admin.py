from django.contrib import admin

from .models import (
    CommunityContribution,
    CommunityGroup,
    ContextEntry,
    FeedbackPrompt,
    FeedbackResponse,
    GlossaryTerm,
    Membership,
    Post,
    SourceFeed,
)


class SourceFeedInline(admin.TabularInline):
    model = SourceFeed
    extra = 0
    fields = ["name", "url", "kind", "is_active", "last_fetched_at"]
    readonly_fields = ["last_fetched_at"]


@admin.register(CommunityGroup)
class CommunityGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "kind", "municipality", "is_active"]
    list_filter = ["kind", "is_active"]
    search_fields = ["name", "slug", "municipality"]
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ["interests"]
    inlines = [SourceFeedInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "community", "role", "created_at"]
    list_filter = ["role", "community"]
    search_fields = ["user__email"]


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["id", "community", "author", "kind", "parent", "created_at"]
    list_filter = ["kind", "community"]
    search_fields = ["body", "author__email"]
    raw_id_fields = ["parent", "author"]


@admin.register(CommunityContribution)
class CommunityContributionAdmin(admin.ModelAdmin):
    list_display = ["id", "community", "kind", "status", "occurrence_count", "is_story_candidate", "created_at"]
    list_filter = ["kind", "status", "is_story_candidate", "community"]
    search_fields = ["body"]
    raw_id_fields = ["author", "linked_snippet"]
    readonly_fields = ["normalized_body"]


@admin.register(SourceFeed)
class SourceFeedAdmin(admin.ModelAdmin):
    list_display = ["name", "community", "kind", "url", "is_active", "last_fetched_at"]
    list_filter = ["kind", "is_active", "community"]
    search_fields = ["name", "url"]


@admin.register(GlossaryTerm)
class GlossaryTermAdmin(admin.ModelAdmin):
    list_display = ["term_fi", "term", "language", "community"]
    list_filter = ["language", "community"]
    search_fields = ["term_fi", "term"]


@admin.register(ContextEntry)
class ContextEntryAdmin(admin.ModelAdmin):
    list_display = ["topic", "language", "community", "valid_from", "reviewed_at", "reviewed_by"]
    list_filter = ["language", "community"]
    search_fields = ["topic", "body"]


class FeedbackResponseInline(admin.TabularInline):
    model = FeedbackResponse
    extra = 0
    readonly_fields = ["user", "snippet", "useful", "missing", "rating", "created_at"]


@admin.register(FeedbackPrompt)
class FeedbackPromptAdmin(admin.ModelAdmin):
    list_display = ["question", "community", "language", "is_active"]
    list_filter = ["language", "is_active", "community"]
    inlines = [FeedbackResponseInline]


@admin.register(FeedbackResponse)
class FeedbackResponseAdmin(admin.ModelAdmin):
    list_display = ["prompt", "user", "snippet", "rating", "created_at"]
    list_filter = ["prompt"]
    raw_id_fields = ["user", "snippet"]
