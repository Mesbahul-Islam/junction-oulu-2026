"""The story desks. Each takes the story so far and returns its part plus any issues.

An issue is ``{"desk", "text", "blocking"}``. A blocking issue means a person must read the
story before it goes out ("Needs review"); a note is shown but doesn't hold it back. No desk
touches the database, so they are easy to follow and to test by hand.
"""

from __future__ import annotations

import re

from apps.common.choices import SAMI_LANGUAGES, ReaderSituation
from apps.editorial import checklist

from ..graph.text import (
    LANGUAGE_LABELS,
    heuristic_risk,
    jaccard,
    language_problem,
    normalize_digits,
    sentences,
    truncate,
)
from . import ai

SITUATIONS = [s.value for s in ReaderSituation]
SITUATION_HINTS = {
    "newcomer": "someone who moved to Finland recently",
    "seasonal_worker": "a seasonal worker here for a few months",
    "student": "a university or vocational student",
    "resident": "a long-time local resident",
}


def issue(desk: str, text: str, blocking: bool) -> dict:
    return {"desk": desk, "text": text, "blocking": blocking}


# --- Reporter --------------------------------------------------------------------------


def reporter(story: dict) -> dict:
    """Finnish headline, short summary and key facts, from the source only."""
    src = story["source"]
    data, problem = ai.ask_json(
        "reporter",
        "You are a reporter at a local newsroom in Oulu, Finland. Write a short Finnish news item for a "
        "community news app from the article below. Use only facts that are in the article; don't add "
        "opinions, advice or anything you aren't told.\n"
        "- headline: neutral, clear Finnish, under 100 characters\n"
        "- summary: 2-3 plain Finnish sentences\n"
        "- key_facts: a list of 2-5 short Finnish facts (dates, times, places, numbers, who)\n\n"
        f"ARTICLE TITLE: {src['title']}\nARTICLE TEXT: {truncate(src['body'], 3500)}",
        ["headline", "summary", "key_facts"],
    )
    issues = []
    if data and str(data.get("headline", "")).strip() and str(data.get("summary", "")).strip():
        facts = data.get("key_facts") or []
        draft = {
            "headline": str(data["headline"]).strip()[:200],
            "summary": str(data["summary"]).strip(),
            "key_facts": [str(f).strip() for f in (facts if isinstance(facts, list) else [facts]) if str(f).strip()][:6],
        }
    else:
        # Fallback: the article's own title and first sentences, so nothing is invented.
        sents = sentences(src["body"])
        draft = {"headline": truncate(src["title"], 120), "summary": truncate(" ".join(sents[:2]) or src["body"], 400),
                 "key_facts": [truncate(s, 160) for s in sents[2:5]]}
        issues.append(issue("reporter", f"The AI reporter couldn't write it ({problem or 'empty answer'}); "
                                        "the draft is the article's own first sentences.", True))
    return {"draft": draft, "issues": issues}


# --- Explainer ---------------------------------------------------------------------------


def explainer(story: dict) -> dict:
    """What the story means for each kind of reader, in Finnish."""
    d = story["draft"]
    who = "\n".join(f"- {k}: {v}" for k, v in SITUATION_HINTS.items())
    data, problem = ai.ask_json(
        "explainer",
        "For each reader below, write one or two plain Finnish sentences on what this news means for them. "
        "Use only the news itself; if it doesn't affect them, say so briefly. No legal or medical advice.\n"
        f"READERS:\n{who}\n\nHEADLINE: {d['headline']}\nSUMMARY: {d['summary']}\nFACTS: {'; '.join(d['key_facts'])}",
        SITUATIONS,
    )
    if data:
        return {"explainer": {k: str(data.get(k, "")).strip() for k in SITUATIONS}, "issues": []}
    return {"explainer": {}, "issues": [issue("explainer", f"No 'what this means for you' text ({problem}).", False)]}


# --- Translator --------------------------------------------------------------------------


def translate_one(story: dict, lang: str) -> tuple[dict | None, str]:
    d, ex = story["draft"], story.get("explainer") or {}
    name = LANGUAGE_LABELS.get(lang, lang)
    fields = ["headline", "summary", "key_facts"] + [k for k in SITUATIONS if ex.get(k)]
    source = {"headline": d["headline"], "summary": d["summary"], "key_facts": d["key_facts"],
              **{k: ex[k] for k in SITUATIONS if ex.get(k)}}
    data, problem = ai.ask_json(
        "translator",
        f"Translate every value of this JSON from Finnish into {name}. Keep names of people, places and "
        "organisations, and every number, date and time exactly. Translate faithfully; add nothing.\n\n"
        f"{source}",
        fields,
    )
    if not data:
        return None, problem
    text = f"{data.get('headline', '')}\n{data.get('summary', '')}"
    wrong = language_problem(text, lang)
    if wrong or jaccard(text, f"{d['headline']}\n{d['summary']}") > 0.6:
        return None, wrong or "the answer was the Finnish text, not a translation"
    facts = data.get("key_facts") or []
    return {
        "headline": str(data["headline"]).strip()[:200],
        "summary": str(data["summary"]).strip(),
        "key_facts": [str(f).strip() for f in (facts if isinstance(facts, list) else [facts]) if str(f).strip()],
        "explainer": {k: str(data.get(k, "")).strip() for k in SITUATIONS if ex.get(k)},
    }, ""


def translator_languages(story: dict) -> tuple[list[str], list[str]]:
    """(machine-translated languages, Sámi languages left for a human translator)."""
    targets = [lang for lang in story["languages"] if lang != "fi"]
    return [lang for lang in targets if lang not in SAMI_LANGUAGES], [lang for lang in targets if lang in SAMI_LANGUAGES]


# --- Fact-checker ------------------------------------------------------------------------

_NUM_RE = re.compile(r"\d+")
_MONTHS = ["tammi", "helmi", "maalis", "huhti", "touko", "kesä", "heinä", "elo", "syys", "loka", "marras", "joulu"]


def _numbers(text: str) -> set[str]:
    """The separate numbers in a text ("1 200" counts as 1200; "24.10." as 24 and 10), plus the
    month numbers of Finnish month names, so "24. lokakuuta" also covers "24.10."."""
    low = re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d{3}\b)", "", normalize_digits(text or "")).lower()
    nums = {n.lstrip("0") or "0" for n in _NUM_RE.findall(low)}
    nums |= {str(i + 1) for i, m in enumerate(_MONTHS) if f"{m}kuu" in low}
    return nums


def fact_checker(story: dict) -> dict:
    """Every number in the Finnish draft must appear in the article (years aside); each
    translation is in its language (checked by the translator) and should keep the numbers."""
    from django.utils import timezone

    d, src = story["draft"], story["source"]
    draft_text = " ".join([d["headline"], d["summary"], *d["key_facts"]])
    year = timezone.now().year
    known = _numbers(f"{src['title']} {src['body']}") | {str(year), str(year + 1)}
    invented = sorted(n for n in _numbers(draft_text) - known if len(n) > 1)
    issues = []
    if invented:
        issues.append(issue("fact_checker", f"The draft has numbers the article doesn't: {', '.join(invented[:6])}.", True))
    draft_nums = {n for n in _numbers(draft_text) if len(n) > 1}
    for lang, v in (story.get("translations") or {}).items():
        lost = sorted(draft_nums - _numbers(" ".join([v["headline"], v["summary"], *v["key_facts"]])))
        if lost:
            issues.append(issue("fact_checker", f"{LANGUAGE_LABELS.get(lang, lang)} version may be missing {', '.join(lost[:4])}.", False))
    return {"issues": issues}


# --- Standards editor --------------------------------------------------------------------

HIGH_RISK_LABEL = "A high-stakes topic (residence permits, health, legal matters, safety): an editor reads it first."


def standards(story: dict) -> dict:
    """JSN checks a person must confirm, and the risk tier."""
    src, d = story["source"], story["draft"]
    text = " ".join([src["title"], src["body"], d["headline"], d["summary"]])
    risk, _hits = heuristic_risk(text)
    issues = []
    if risk == "high":
        issues.append(issue("standards", HIGH_RISK_LABEL, True))
    sensitive = checklist.detect(text)
    for key in sensitive:
        issues.append(issue("standards", "JSN check: " + checklist.SENSITIVE_CHECKS[key]["label"], True))
    if re.search(r"!|\b(shokki|järkyttä|uskomaton|et usko)\b", d["headline"], re.I):
        issues.append(issue("standards", "The headline may sound sensational.", False))
    return {"risk": risk, "sensitive": sensitive, "issues": issues}
