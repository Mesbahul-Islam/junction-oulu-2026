from django.contrib import admin

from .models import CommunityNote, NoteRating


class NoteRatingInline(admin.TabularInline):
    model = NoteRating
    extra = 0
    raw_id_fields = ["rater"]


@admin.register(CommunityNote)
class CommunityNoteAdmin(admin.ModelAdmin):
    list_display = ["id", "claim_summary", "snippet", "post", "status", "created_at"]
    list_filter = ["status"]
    raw_id_fields = ["snippet", "post", "author"]
    inlines = [NoteRatingInline]


@admin.register(NoteRating)
class NoteRatingAdmin(admin.ModelAdmin):
    list_display = ["note", "rater", "value", "created_at"]
    list_filter = ["value"]
