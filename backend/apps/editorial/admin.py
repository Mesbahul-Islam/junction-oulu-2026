from django.contrib import admin

from .models import AuditLogEntry, Correction, ReviewTask, StandardsCheck, VerificationResult


@admin.register(ReviewTask)
class ReviewTaskAdmin(admin.ModelAdmin):
    list_display = ["id", "snippet", "required_role", "language", "reason", "priority", "status", "active"]
    list_filter = ["status", "reason", "required_role", "language", "active"]
    raw_id_fields = ["snippet", "assigned_to", "decided_by"]


@admin.register(VerificationResult)
class VerificationResultAdmin(admin.ModelAdmin):
    list_display = ["snippet", "language", "passed", "confidence", "created_at"]
    list_filter = ["passed", "language"]
    raw_id_fields = ["snippet"]


@admin.register(StandardsCheck)
class StandardsCheckAdmin(admin.ModelAdmin):
    list_display = ["snippet", "passed", "created_at"]
    raw_id_fields = ["snippet"]


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ["created_at", "snippet", "action", "actor", "agent"]
    list_filter = ["action", "agent"]
    raw_id_fields = ["snippet", "actor"]

    def has_change_permission(self, request, obj=None):  # append-only
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Correction)
class CorrectionAdmin(admin.ModelAdmin):
    list_display = ["snippet", "language", "what_changed", "published_at"]
    raw_id_fields = ["snippet", "approved_by"]
