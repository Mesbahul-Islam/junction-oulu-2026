"""Translator agent - newsroom role: **translation desk** (FR-3.9).

Human counterpart (FR-3.6): the native-language reviewer, who approves each
language version separately.
Translates the Finnish draft into every target language of the community
using the community glossary (``communities.GlossaryTerm``: Kela, Migri,
verokortti ...). Background text prefers a reviewed ``ContextEntry`` that
already exists in the target language over a translation.

**Sámi rule (FR-3.9):** this agent NEVER produces Sámi text. For every
language in ``SAMI_LANGUAGES`` it creates an empty placeholder version marked
``needs_human_translation`` so editorial routes it to a human translator.
"""

from __future__ import annotations

import re
from typing import Any

from apps.common.choices import SAMI_LANGUAGES, Language

from ..llm import structured_call
from ..schemas import TranslationOut
from ..state import NewsroomState

SAMI_CODES = {str(getattr(lang, "value", lang)) for lang in SAMI_LANGUAGES}
LANGUAGE_NAMES = {lang.value: lang.label for lang in Language}


def sami_placeholder() -> dict:
    return {
        "headline": "",
        "summary": "",
        "key_facts": [],
        "explainer": {},
        "background": "",
        "is_machine_translated": False,
        "needs_human_translation": True,
    }


def glossary_for(glossary: list[dict], lang: str) -> list[dict]:
    return [g for g in glossary if g.get("language") == lang and g.get("term_fi") and g.get("term")]


def apply_glossary(text: str, terms: list[dict]) -> str:
    for g in terms:
        text = re.sub(re.escape(g["term_fi"]), g["term"], text, flags=re.IGNORECASE)
    return text


def stub_translation(draft: dict, lang: str, terms: list[dict]) -> TranslationOut:
    """Offline stand-in: marks text with the language code (clearly not a real
    translation) and applies glossary substitutions."""

    def tr(s: str) -> str:
        return f"[{lang}] {apply_glossary(s, terms)}" if s else ""

    return TranslationOut(
        headline=tr(draft.get("headline", "")),
        summary=tr(draft.get("summary", "")),
        key_facts=[tr(f) for f in draft.get("key_facts", [])],
        explainer={k: tr(v) for k, v in (draft.get("explainer") or {}).items()},
        background=tr(draft.get("background", "")),
    )


def translate_draft(draft: dict, lang: str, glossary: list[dict], errors: list) -> dict:
    terms = glossary_for(glossary, lang)
    gloss_txt = "\n".join(f"- {g['term_fi']} => {g['term']}" + (f" ({g['note']})" if g.get("note") else "") for g in terms)
    prompt = (
        f"Translate this Finnish news snippet into {LANGUAGE_NAMES.get(lang, lang)} ({lang}).\n"
        "Rules: translate faithfully, plain language, keep every number, time and date exactly "
        "(dates as dd.mm.yyyy), keep names of people/places/organisations, use the glossary terms "
        "below exactly, do not add or remove information. Keep the explainer keys unchanged.\n"
        f"GLOSSARY:\n{gloss_txt or '(none)'}\n\n"
        f"HEADLINE: {draft.get('headline', '')}\nSUMMARY: {draft.get('summary', '')}\n"
        f"KEY_FACTS: {draft.get('key_facts', [])}\nEXPLAINER: {draft.get('explainer', {})}\n"
        f"BACKGROUND: {draft.get('background', '')}"
    )
    out = structured_call(
        prompt, TranslationOut, lambda: stub_translation(draft, lang, terms), errors=errors, agent="translator"
    )
    return {
        "headline": out.headline.strip(),
        "summary": out.summary.strip(),
        "key_facts": [f.strip() for f in out.key_facts if f and f.strip()],
        "explainer": {k: (v or "").strip() for k, v in out.explainer.model_dump().items() if k in (draft.get("explainer") or {})},
        "background": (out.background or "").strip() if draft.get("background") else "",
        "is_machine_translated": True,
        "needs_human_translation": False,
    }


def translator(state: NewsroomState) -> dict[str, Any]:
    errors: list[dict] = []
    targets = state.get("language_targets") or []
    glossary = state.get("glossary") or []
    entries = {e.get("id"): e for e in state.get("context_entries") or []}
    translations: dict[str, dict[str, dict]] = {}

    for key, draft in (state.get("drafts") or {}).items():
        per_lang: dict[str, dict] = {}
        for lang in targets:
            if lang in SAMI_CODES:
                per_lang[lang] = sami_placeholder()  # FR-3.9: never machine-translate Sámi
                continue
            version = translate_draft(draft, lang, glossary, errors)
            # Prefer a reviewed context entry already written in the target language.
            topics = {entries[i].get("topic") for i in draft.get("background_context_ids", []) if i in entries}
            native = [e for e in entries.values() if e.get("language") == lang and e.get("topic") in topics]
            if native:
                version["background"] = "\n\n".join(e["body"].strip() for e in native)
            per_lang[lang] = version
        translations[key] = per_lang

    return {"translations": translations, "errors": list(state.get("errors") or []) + errors}
