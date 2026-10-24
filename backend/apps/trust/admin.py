from django.contrib import admin, messages

from .models import MemberTrust
from .services import can_decide, decide


@admin.register(MemberTrust)
class MemberTrustAdmin(admin.ModelAdmin):
    list_display = ["user", "community", "score", "verified", "level", "approved_by", "approved_at"]
    list_filter = ["level", "community"]
    search_fields = ["user__username", "user__email"]
    readonly_fields = ["score", "verified", "breakdown", "approved_by", "approved_at", "declined_at"]
    actions = ["approve", "decline"]

    def _decide(self, request, queryset, approve):
        done = 0
        for trust in queryset.select_related("community"):
            if not can_decide(request.user, trust.community):
                continue
            try:
                decide(trust, request.user, approve)
                done += 1
            except ValueError as exc:
                self.message_user(request, f"{trust.user}: {exc}", messages.WARNING)
        self.message_user(request, f"{done} decided.")

    @admin.action(description="Approve as trusted voice")
    def approve(self, request, queryset):
        self._decide(request, queryset, True)

    @admin.action(description="Decline / remove trusted voice")
    def decline(self, request, queryset):
        self._decide(request, queryset, False)
