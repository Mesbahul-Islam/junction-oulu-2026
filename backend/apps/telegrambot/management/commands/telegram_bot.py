"""Listen for Telegram messages (long polling) and run the onboarding conversation.

No public URL is needed: the bot asks Telegram for new messages. Runs as the `telegram`
service in docker-compose. Without a token (TELEGRAM_API) it waits and does nothing.

    manage.py telegram_bot
"""

import logging
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.telegrambot import api
from apps.telegrambot.flow import handle_update

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the Telegram news bot (onboarding conversation)"

    def handle(self, *args, **opts):
        if not settings.TELEGRAM_BOT_TOKEN:
            self.stdout.write("No TELEGRAM_API token set; the Telegram bot is idle.")
            while True:
                time.sleep(3600)
        me = api.call("getMe")
        self.stdout.write(self.style.SUCCESS(f"Telegram bot @{(me or {}).get('username', '?')} listening."))
        api.call("setMyCommands", commands=[{"command": "start", "description": "Set up your news"},
                                             {"command": "stop", "description": "Stop and delete my details"}])
        offset = None
        while True:
            try:
                params = {"offset": offset} if offset else {}
                updates = api.call("getUpdates", http_timeout=40, timeout=30,
                                   allowed_updates=["message", "callback_query"], **params)
            except Exception as exc:  # network hiccup: wait and try again
                logger.warning("Telegram polling failed: %s", exc)
                time.sleep(5)
                continue
            for update in updates or []:
                offset = update["update_id"] + 1
                try:
                    handle_update(update)
                except Exception:
                    logger.exception("Telegram update failed: %s", update.get("update_id"))
