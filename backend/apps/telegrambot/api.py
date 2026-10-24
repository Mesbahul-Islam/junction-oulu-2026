"""The few Telegram Bot API calls the bot needs (https://core.telegram.org/bots/api)."""

from __future__ import annotations

import logging

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class Blocked(Exception):
    """The reader blocked the bot or deleted the chat."""


def call(method: str, http_timeout: float = 15, **params) -> dict | list | bool | None:
    """Call a Bot API method. `http_timeout` is ours; Telegram's own `timeout` (long polling) goes in params."""
    token = settings.TELEGRAM_BOT_TOKEN
    resp = httpx.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=http_timeout)
    data = resp.json()
    if not data.get("ok"):
        if resp.status_code == 403:
            raise Blocked(data.get("description", ""))
        logger.warning("Telegram %s failed: %s", method, data.get("description"))
        return None
    return data["result"]


def keyboard(rows: list[list[tuple[str, str]]]) -> dict:
    """[[(label, callback_data), ...], ...] -> inline keyboard markup."""
    return {"inline_keyboard": [[{"text": label, "callback_data": data} for label, data in row] for row in rows]}


def send(chat_id: int, text: str, buttons: list | None = None, preview: bool = False):
    params = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "link_preview_options": {"is_disabled": not preview}}
    if buttons is not None:
        params["reply_markup"] = keyboard(buttons)
    return call("sendMessage", **params)


def edit(chat_id: int, message_id: int, text: str, buttons: list | None = None):
    params = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if buttons is not None:
        params["reply_markup"] = keyboard(buttons)
    return call("editMessageText", **params)


def answer(callback_id: str, text: str = "", alert: bool = False):
    return call("answerCallbackQuery", callback_query_id=callback_id, text=text, show_alert=alert)
