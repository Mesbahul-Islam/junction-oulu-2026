"""Synthesizer agent - newsroom role: **reporter / rewrite desk** (FR-3.2).

Human counterpart (FR-3.6): the editor (synthesizer + explainer output is
edited by an editor before anything is published).
Turns each assigned source item into a Finnish (source-language) draft:
headline, short summary and 3-5 key facts. Facts must be copied faithfully
from the source; the fact-checker later verifies every number/date/name.
"""

from __future__ import annotations

import re
from typing import Any

from apps.common.choices import SOURCE_LANGUAGE

from ..llm import structured_call
from ..schemas import DraftOut
from ..state import NewsroomState
from ..text import sentences, truncate

_FACTY = re.compile(r"\d|klo|alkaen|asti|mennessä|until|from", re.I)


def stub_draft(title: str, body: str) -> DraftOut:
    sents = sentences(body)
    headline = truncate(title or (sents[0] if sents else ""), 90)
    summary = truncate(" ".join(sents[:2]) if sents else body, 400)
    facts = [truncate(s, 160) for s in sents if _FACTY.search(s)][:4]
    if len(facts) < 3:
        for s in sents:
            s = truncate(s, 160)
            if s not in facts:
                facts.append(s)
            if len(facts) >= 3:
                break
    return DraftOut(headline=headline, summary=summary, key_facts=facts)


def synthesizer(state: NewsroomState) -> dict[str, Any]:
    errors: list[dict] = []
    raw = {r["key"]: r for r in state.get("raw_items") or []}
    src_lang = state.get("source_language") or SOURCE_LANGUAGE.value
    drafts: dict[str, dict] = {}

    for key in (state.get("assignments") or {}):
        item = raw.get(key)
        if not item:
            continue
        title, body = item.get("title", ""), item.get("body", "")
        prompt = (
            "Write a short Finnish news snippet from the source below for a local community feed.\n"
            "- headline: neutral, max 90 characters, no clickbait, no exclamation marks\n"
            "- summary: 2-3 plain-language sentences (selkokieli where possible)\n"
            "- key_facts: 3-5 short facts copied faithfully (dates, times, places, numbers, who)\n"
            "Use ONLY information in the source. Do not add background or advice.\n\n"
            f"SOURCE TITLE: {title}\nSOURCE PUBLISHER: {item.get('publisher', '')}\n"
            f"SOURCE TEXT:\n{truncate(body, 6000)}"
        )
        out = structured_call(prompt, DraftOut, lambda t=title, b=body: stub_draft(t, b), errors=errors, agent="synthesizer")
        drafts[key] = {
            "language": src_lang,
            "headline": out.headline.strip(),
            "summary": out.summary.strip(),
            "key_facts": [f.strip() for f in out.key_facts if f and f.strip()][:5],
        }

    return {"drafts": drafts, "errors": list(state.get("errors") or []) + errors}
