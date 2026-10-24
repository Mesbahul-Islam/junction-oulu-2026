"""Onboarding in the chat: the app's four steps (language, topics, situation and arrival,
communities), answered with buttons. Saved through accounts.services.complete_onboarding, the
same function the app's onboarding uses. After that the bot only sends news; typed messages are
ignored, except /stop, which deletes the reader and their account.
"""

from __future__ import annotations

import html
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Interest
from apps.accounts.services import complete_onboarding
from apps.common.choices import Language, ReaderSituation

from . import api
from .models import TelegramReader

LANGUAGES = [("fi", "Suomi"), ("en", "English"), ("sv", "Svenska"), ("uk", "Українська"), ("ru", "Русский"),
             ("ar", "العربية"), ("so", "Soomaali"), ("et", "Eesti"), ("se", "Davvisámegiella"),
             ("smn", "Anarâškielâ"), ("sms", "Sääʹmǩiõll")]
# Months since arrival -> button. "Skip" leaves the arrival date empty, as in the app.
ARRIVAL = [(1, "arr_recent"), (6, "arr_months"), (18, "arr_year")]

TEXT = {
    "en": {
        "welcome": "Choose your language. The news will come in this language.",
        "topics": "What do you want to follow? Pick one or more, then tap Continue.",
        "pick_one": "Pick at least one topic.",
        "continue": "Continue",
        "situation": "Which fits you best?",
        "newcomer": "I just moved to Finland", "student": "I'm a student",
        "seasonal_worker": "I'm a seasonal worker", "resident": "I've lived here a while",
        "arrival": "When did you arrive in Finland? It helps flag deadlines in your first months.",
        "arr_recent": "Less than 3 months ago", "arr_months": "3 to 12 months ago", "arr_year": "Over a year ago",
        "skip": "Skip",
        "communities": "Join communities near you? Their news comes with yours.",
        "done_button": "Done",
        "done": "You're set. Every morning you'll get the stories that matter most to you, in {language}. Send /stop at any time to stop and delete your details.",
        "stopped": "Stopped. Your details are deleted.",
        "first": "Here is today's news for you:",
        "language": "Language", "topics_label": "Topics", "situation_label": "Situation", "arrival_label": "Arrived",
        "communities_label": "Communities", "none": "none",
    },
    "fi": {
        "welcome": "Valitse kieli. Uutiset tulevat tällä kielellä.",
        "topics": "Mitä haluat seurata? Valitse yksi tai useampi ja paina Jatka.",
        "pick_one": "Valitse vähintään yksi aihe.",
        "continue": "Jatka",
        "situation": "Mikä kuvaa sinua parhaiten?",
        "newcomer": "Muutin juuri Suomeen", "student": "Olen opiskelija",
        "seasonal_worker": "Olen kausityöntekijä", "resident": "Olen asunut täällä pitkään",
        "arrival": "Milloin muutit Suomeen? Näin muistutamme ensimmäisten kuukausien määräajoista.",
        "arr_recent": "Alle 3 kuukautta sitten", "arr_months": "3–12 kuukautta sitten", "arr_year": "Yli vuosi sitten",
        "skip": "Ohita",
        "communities": "Liitytkö lähialueen yhteisöihin? Niiden uutiset tulevat omiesi mukana.",
        "done_button": "Valmis",
        "done": "Valmista. Saat joka aamu sinulle tärkeimmät uutiset kielellä {language}. Lähetä /stop milloin vain, niin lopetamme ja poistamme tietosi.",
        "stopped": "Lopetettu. Tietosi on poistettu.",
        "first": "Tässä tämän päivän uutiset sinulle:",
        "language": "Kieli", "topics_label": "Aiheet", "situation_label": "Tilanne", "arrival_label": "Saapunut",
        "communities_label": "Yhteisöt", "none": "ei",
    },
}
WELCOME_ALL = ("Choose your language · Valitse kieli · Välj språk · Оберіть мову · Выберите язык · اختر لغتك")


def t(reader: TelegramReader, key: str) -> str:
    lang = reader.draft.get("language") or reader.user.preferred_language
    return TEXT.get(lang if lang in TEXT else "en")[key]


def language_name(code: str) -> str:
    return dict(LANGUAGES).get(code, code)


# --- Keyboards ---

def language_buttons():
    return [[(name, f"lang:{code}") for code, name in LANGUAGES[i:i + 2]] for i in range(0, len(LANGUAGES), 2)]


def topic_buttons(reader):
    picked = set(reader.draft.get("interests", []))
    topics = list(Interest.objects.filter(parent__isnull=True).order_by("name"))
    rows = [[(("✓ " if i.slug in picked else "") + i.name, f"topic:{i.slug}") for i in topics[n:n + 2]]
            for n in range(0, len(topics), 2)]
    return rows + [[(t(reader, "continue"), "topics:done")]]


def situation_buttons(reader):
    return [[(t(reader, s), f"sit:{s}")] for s in ReaderSituation.values]


def arrival_buttons(reader):
    return [[(t(reader, key), f"arr:{months}")] for months, key in ARRIVAL] + [[(t(reader, "skip"), "arr:skip")]]


def community_buttons(reader):
    picked = set(reader.draft.get("communities", []))
    return [[(("✓ " if c["id"] in picked else "") + c["name"], f"com:{c['id']}")] for c in reader.draft.get("offer", [])] \
        + [[(t(reader, "done_button"), "coms:done")]]


# --- Reader ---

def reader_for(chat: dict) -> TelegramReader:
    """The reader for this chat, creating their account on first contact."""
    found = TelegramReader.objects.select_related("user").filter(chat_id=chat["id"]).first()
    if found:
        return found
    User = get_user_model()
    user = User.objects.create_user(
        email=f"tg{chat['id']}@telegram.invalid",  # never mailed; .invalid is a reserved domain
        display_name=" ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))[:120],
        onboarded=False,
    )
    return TelegramReader.objects.create(chat_id=chat["id"], user=user)


def summary_line(reader, label_key: str, value: str) -> str:
    return f"{t(reader, label_key)}: <b>{html.escape(value)}</b>"


# --- Updates ---

def handle_update(update: dict) -> None:
    if "message" in update:
        handle_message(update["message"])
    elif "callback_query" in update:
        handle_button(update["callback_query"])


def handle_message(message: dict) -> None:
    chat = message.get("chat", {})
    if chat.get("type") != "private":
        return
    text = (message.get("text") or "").strip()
    existing = TelegramReader.objects.select_related("user").filter(chat_id=chat["id"]).first()
    if text.startswith("/stop"):
        if existing:
            stop(existing)
        return
    if existing and existing.step == TelegramReader.Step.DONE:
        return  # after onboarding the bot only sends news
    reader = existing or reader_for(chat)
    if not existing or text.startswith("/start"):
        reader.step, reader.draft = TelegramReader.Step.LANGUAGE, {}
        reader.save(update_fields=["step", "draft", "updated_at"])
    ask(reader)  # anything typed during onboarding: show the current question again


def ask(reader: TelegramReader, message_id: int | None = None) -> None:
    """Send (or replace) the question for the reader's current step."""
    step = reader.step
    S = TelegramReader.Step
    text, buttons = {
        S.LANGUAGE: (WELCOME_ALL, language_buttons),
        S.TOPICS: (t(reader, "topics"), topic_buttons),
        S.SITUATION: (t(reader, "situation"), situation_buttons),
        S.ARRIVAL: (t(reader, "arrival"), arrival_buttons),
        S.COMMUNITIES: (t(reader, "communities"), community_buttons),
    }[step]
    rows = buttons() if step == S.LANGUAGE else buttons(reader)
    if message_id:
        api.edit(reader.chat_id, message_id, text, rows)
    else:
        api.send(reader.chat_id, text, rows)


def handle_button(query: dict) -> None:
    chat = query.get("message", {}).get("chat", {})
    message_id = query.get("message", {}).get("message_id")
    reader = TelegramReader.objects.select_related("user").filter(chat_id=chat.get("id")).first()
    if reader is None or reader.step == TelegramReader.Step.DONE:
        api.answer(query["id"])
        return
    kind, _, value = (query.get("data") or "").partition(":")
    S = TelegramReader.Step
    draft = reader.draft

    if kind == "lang" and reader.step == S.LANGUAGE and value in Language.values:
        draft["language"] = value
        api.edit(reader.chat_id, message_id, summary_line(reader, "language", language_name(value)))
        next_step(reader, S.TOPICS)
    elif kind == "topic" and reader.step == S.TOPICS:
        picked = set(draft.get("interests", []))
        picked ^= {value}
        draft["interests"] = sorted(picked)
        reader.save(update_fields=["draft", "updated_at"])
        ask(reader, message_id)  # redraw the ticks
    elif kind == "topics" and reader.step == S.TOPICS:
        if not draft.get("interests"):
            api.answer(query["id"], t(reader, "pick_one"), alert=True)
            return
        names = Interest.objects.filter(slug__in=draft["interests"]).values_list("name", flat=True)
        api.edit(reader.chat_id, message_id, summary_line(reader, "topics_label", ", ".join(names)))
        next_step(reader, S.SITUATION)
    elif kind == "sit" and reader.step == S.SITUATION and value in ReaderSituation.values:
        draft["situation"] = value
        api.edit(reader.chat_id, message_id, summary_line(reader, "situation_label", t(reader, value)))
        next_step(reader, S.ARRIVAL)
    elif kind == "arr" and reader.step == S.ARRIVAL:
        label = t(reader, "skip")
        if value.isdigit():
            draft["arrival_date"] = (timezone.localdate() - timedelta(days=30 * int(value))).isoformat()
            label = t(reader, dict(ARRIVAL)[int(value)])
        api.edit(reader.chat_id, message_id, summary_line(reader, "arrival_label", label))
        save_profile(reader)
        offer = recommended(reader)
        if offer:
            draft["offer"] = offer
            next_step(reader, S.COMMUNITIES)
        else:
            finish(reader)
    elif kind == "com" and reader.step == S.COMMUNITIES and value.isdigit():
        picked = set(draft.get("communities", []))
        picked ^= {int(value)}
        draft["communities"] = sorted(picked)
        reader.save(update_fields=["draft", "updated_at"])
        ask(reader, message_id)
    elif kind == "coms" and reader.step == S.COMMUNITIES:
        names = join_picked(reader)
        api.edit(reader.chat_id, message_id, summary_line(reader, "communities_label", ", ".join(names) or t(reader, "none")))
        finish(reader)
    api.answer(query["id"])


def next_step(reader: TelegramReader, step: str) -> None:
    reader.step = step
    reader.save(update_fields=["step", "draft", "updated_at"])
    ask(reader)


def save_profile(reader: TelegramReader) -> None:
    """Exactly what the app's onboarding saves."""
    d = reader.draft
    complete_onboarding(reader.user, {
        "preferred_language": d["language"], "interests": d["interests"],
        "reader_situation": d["situation"], "arrival_date": d.get("arrival_date"),
    })


def recommended(reader: TelegramReader) -> list[dict]:
    from apps.communities.services import recommend_communities

    return [{"id": g.pk, "name": g.name} for g, _, _ in recommend_communities(reader.user)]


def join_picked(reader: TelegramReader) -> list[str]:
    from apps.communities.models import CommunityGroup
    from apps.communities.services import join_community

    names = []
    for group in CommunityGroup.objects.filter(pk__in=reader.draft.get("communities", [])):
        join_community(reader.user, group)
        names.append(group.name)
    return names


def finish(reader: TelegramReader) -> None:
    from .digest import send_digest

    reader.step, reader.draft = TelegramReader.Step.DONE, {}
    reader.save(update_fields=["step", "draft", "updated_at"])
    api.send(reader.chat_id, t(reader, "done").format(language=language_name(reader.user.preferred_language)))
    send_digest(reader, intro=t(reader, "first"))


@transaction.atomic
def stop(reader: TelegramReader) -> None:
    """Stop the news and delete the reader and their account."""
    lang = reader.user.preferred_language
    chat_id = reader.chat_id
    reader.user.delete()  # cascades to the TelegramReader
    api.send(chat_id, TEXT.get(lang if lang in TEXT else "en")["stopped"])
