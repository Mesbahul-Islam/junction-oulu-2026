"""Serve analysis and coach notes instantly; polish them with AI in the background.

A request always gets the plain, data-built version straight away (fast, no model call). If an
AI-polished version is stored for the same situation, that is returned instead; if not, a
background job is queued to make one, so the next visit gets it.
"""

from __future__ import annotations

from django.core.cache import cache

from ..models import Fixture, Report, Squad
from . import analysis


# Lämäri runs nothing in the background for now: no AI polish jobs are queued, so pages show the
# plain data-built version (or an AI version stored earlier). Set to True to queue them again.
QUEUE_POLISH = False


def _queue_once(key: str, task, *args) -> None:
    if QUEUE_POLISH and cache.add(f"fx-queued:{key}", 1, 600):  # one job per report per 10 minutes
        task.delay(*args)


def match_key(fixture: Fixture, detail: str, reader: str = "fan", lang: str = "en") -> str:
    return f"match:{fixture.pk}:{detail}:{reader}:{lang}:{fixture.status}"


def match_report(fixture: Fixture, squad: Squad | None, detail: str, reader: str = "fan", lang: str = "en") -> dict:
    from ..tasks import polish_match

    data = analysis.match_analysis(fixture, squad, detail, ai=False, reader=reader, lang=lang)
    key = match_key(fixture, detail, reader, lang)
    stored = Report.objects.filter(key=key).first()
    if stored and stored.wording == "ai" and len(stored.data.get("notes", [])) == len(data["notes"]):
        data["notes"], data["source"] = stored.data["notes"], "ai"
    elif not stored:
        _queue_once(key, polish_match, fixture.pk, detail, reader, lang)
    return data


def coach_key(squad: Squad, data: dict) -> str:
    return f"coach:{squad.pk}:{data.get('lang', 'en')}:{data.get('gameweek')}:{data.get('next_gameweek')}:{len(data['tips'])}"


def coach_report(squad: Squad, lang: str = "en") -> dict:
    from ..tasks import polish_coach

    data = analysis.coach(squad, ai=False, lang=lang)
    key = coach_key(squad, data)
    stored = Report.objects.filter(key=key).first()
    if stored and stored.wording == "ai":
        return stored.data
    if not stored:
        _queue_once(key, polish_coach, squad.pk, lang)
    return data
