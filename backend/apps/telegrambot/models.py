"""Telegram readers: onboarded in the chat with the same questions as the app, then sent news.

Each chat gets a normal reader account (no email or password of its own), so the profile is
saved by accounts.services.complete_onboarding and the feed ranks stories exactly as in the app.
"""

from django.conf import settings
from django.db import models

from apps.common.models import TimeStampedModel


class TelegramReader(TimeStampedModel):
    class Step(models.TextChoices):
        LANGUAGE = "language", "Language"
        TOPICS = "topics", "Topics"
        SITUATION = "situation", "Situation"
        ARRIVAL = "arrival", "Arrival"
        COMMUNITIES = "communities", "Communities"
        DONE = "done", "Receiving news"

    chat_id = models.BigIntegerField(unique=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="telegram")
    step = models.CharField(max_length=12, choices=Step.choices, default=Step.LANGUAGE)
    draft = models.JSONField(default=dict, blank=True)  # answers so far, until onboarding is saved
    active = models.BooleanField(default=True)  # off after /stop or when the reader blocks the bot
    sent_ids = models.JSONField(default=list, blank=True)  # stories already sent, newest last
    last_sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.chat_id} ({self.step})"
