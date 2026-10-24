from django.contrib import admin

from .models import TelegramReader


@admin.register(TelegramReader)
class TelegramReaderAdmin(admin.ModelAdmin):
    list_display = ["chat_id", "user", "step", "active", "last_sent_at", "created_at"]
    list_filter = ["step", "active"]
    readonly_fields = ["chat_id", "user", "draft", "sent_ids", "last_sent_at"]
