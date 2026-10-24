"""The news a Telegram reader gets: the top of their personalised feed (the same ranking as the
app), editor-approved stories only, in their language, never the same story twice."""

from __future__ import annotations

import html
import logging

from django.conf import settings
from django.utils import timezone

from apps.feed import recommend, services
from apps.feed.serializers import SnippetCardSerializer

from . import api
from .models import TelegramReader

logger = logging.getLogger(__name__)

PER_DIGEST = 3
REMEMBER = 200  # story ids kept per reader to avoid repeats
LABEL = {
    "en": {"reviewed": "Reviewed by", "read": "Read in the app", "source": "Kaleva original", "for_you": "For you"},
    "fi": {"reviewed": "Tarkistanut", "read": "Lue sovelluksessa", "source": "Kalevan alkuperäinen", "for_you": "Sinulle"},
}


def stories_for(reader: TelegramReader, limit: int = PER_DIGEST) -> list[dict]:
    user = reader.user
    chain = services.language_chain(user.preferred_language)
    ranked = recommend.rank(services.feed_candidates(chain), user, chain=chain)
    sent = set(reader.sent_ids)
    fresh = [s for s in ranked if s.pk not in sent][:limit]
    return SnippetCardSerializer(fresh, many=True, context={"language_chain": chain, "reader": user}).data


def format_story(card: dict, lang: str) -> str:
    label = LABEL.get(lang, LABEL["en"])
    e = html.escape
    summary = card["summary"] if len(card["summary"]) <= 320 else card["summary"][:317].rsplit(" ", 1)[0] + "…"
    parts = [f"<b>{e(card['headline'])}</b>", e(summary)]
    if card.get("for_you"):
        parts.append(f"<i>{label['for_you']}:</i> {e(card['for_you'])}")
    links = [f'<a href="{e(settings.FRONTEND_URL.rstrip("/"))}/story/{card["id"]}">{label["read"]}</a>']
    if card.get("source_urls"):
        links.append(f'<a href="{e(card["source_urls"][0])}">{label["source"]}</a>')
    parts.append(f"{label['reviewed']} {e(card['author'])} · " + " · ".join(links))
    return "\n\n".join(parts)


def send_digest(reader: TelegramReader, intro: str = "") -> int:
    """Send the next stories to one reader. Returns how many were sent."""
    cards = stories_for(reader)
    if not cards:
        return 0
    lang = reader.user.preferred_language
    try:
        if intro:
            api.send(reader.chat_id, html.escape(intro))
        for card in cards:
            api.send(reader.chat_id, format_story(card, lang))
    except api.Blocked:
        reader.active = False
        reader.save(update_fields=["active", "updated_at"])
        return 0
    reader.sent_ids = (reader.sent_ids + [c["id"] for c in cards])[-REMEMBER:]
    reader.last_sent_at = timezone.now()
    reader.save(update_fields=["sent_ids", "last_sent_at", "updated_at"])
    return len(cards)


def send_all() -> dict:
    """The morning run: every onboarded, active reader."""
    readers = TelegramReader.objects.filter(step=TelegramReader.Step.DONE, active=True).select_related("user")
    sent = 0
    for reader in readers:
        try:
            sent += send_digest(reader)
        except Exception:  # one reader's failure must not stop the rest
            logger.exception("Telegram digest failed for chat %s", reader.chat_id)
    return {"readers": readers.count(), "stories": sent}
