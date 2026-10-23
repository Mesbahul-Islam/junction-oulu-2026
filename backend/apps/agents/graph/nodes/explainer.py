"""Explainer agent - newsroom role: **explainer / service journalist** (FR-3.2, FR-3.8).

Human counterpart (FR-3.6): the editor (together with the synthesizer).
Adds "what this means for me" per ``ReaderSituation`` (newcomer, seasonal
worker, student, resident). Background is taken **only** from the community's
reviewed context library (``communities.ContextEntry``) - never generated -
and kept in a separate, labelled ``background`` field so readers and editors
can tell news from context (FR-3.8).
"""

from __future__ import annotations

from typing import Any

from apps.common.choices import SOURCE_LANGUAGE, ReaderSituation, RiskTier

from ..llm import structured_call
from ..schemas import ExplainerOut
from ..state import NewsroomState
from ..text import tokens, topic_tags, truncate

BACKGROUND_LABEL = "Taustaa toimituksen kontekstikirjastosta (ei osa uutislähdettä)"
MAX_CONTEXT_ENTRIES = 2


def select_context(entries: list[dict], text: str, language: str) -> list[dict]:
    """Pick context-library entries whose topic matches the item text."""
    tags = set(topic_tags(text))
    text_tokens = set(tokens(text))
    scored = []
    for e in entries:
        if e.get("language") and e["language"] != language:
            continue
        topic = (e.get("topic") or "").lower()
        topic_tokens = set(tokens(topic))
        score = 0
        if topic in tags:
            score += 3
        score += len(topic_tokens & (text_tokens | tags))
        if score:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:MAX_CONTEXT_ENTRIES]]


def stub_explainer(headline: str, risk_tier: str, tags: list[str]) -> ExplainerOut:
    headline = headline.rstrip(".?!… ")
    act = (
        "Tarkista, koskeeko muutos sinua, ja toimi annetussa aikataulussa."
        if risk_tier == RiskTier.HIGH.value
        else "Tieto voi vaikuttaa arkeesi lähiaikoina."
    )
    return ExplainerOut(
        newcomer=f"Jos olet juuri muuttanut Suomeen: {headline}. {act} Kysy tarvittaessa neuvontapalvelusta.",
        seasonal_worker=f"Kausityöntekijälle: {headline}. {act}"
        + (" Tarkista myös työnantajaltasi." if "work" in tags else ""),
        student=f"Opiskelijalle: {headline}. {act}"
        + (" Oppilaitoksesi voi antaa lisätietoa." if "education" in tags else ""),
        resident=f"Paikalliselle asukkaalle: {headline}. {act}",
    )


def explainer(state: NewsroomState) -> dict[str, Any]:
    errors: list[dict] = []
    raw = {r["key"]: r for r in state.get("raw_items") or []}
    src_lang = state.get("source_language") or SOURCE_LANGUAGE.value
    entries = state.get("context_entries") or []
    assignments = state.get("assignments") or {}
    drafts = {k: dict(v) for k, v in (state.get("drafts") or {}).items()}

    for key, draft in drafts.items():
        item = raw.get(key, {})
        text = f"{item.get('title', '')} {item.get('body', '')}"
        tags = topic_tags(text)
        risk = assignments.get(key, {}).get("risk_tier", RiskTier.MEDIUM.value)

        context = select_context(entries, text, src_lang)
        if context:
            draft["background"] = "\n\n".join(e["body"].strip() for e in context)
            draft["background_label"] = BACKGROUND_LABEL
            draft["background_context_ids"] = [e["id"] for e in context if e.get("id") is not None]
        else:
            draft["background"] = ""
            draft["background_label"] = ""
            draft["background_context_ids"] = []

        context_txt = "\n".join(f"- [{e.get('topic')}] {truncate(e['body'], 800)}" for e in context) or "(none)"
        prompt = (
            "For the Finnish news snippet below, write in Finnish one or two plain sentences per reader "
            "situation answering 'what does this mean for me?': newcomer, seasonal_worker, student, resident.\n"
            "Use ONLY the snippet, its source and the reviewed context entries. If the news does not affect "
            "a group, say so briefly. No legal or medical advice beyond what the source says.\n\n"
            f"HEADLINE: {draft.get('headline')}\nSUMMARY: {draft.get('summary')}\n"
            f"KEY FACTS: {'; '.join(draft.get('key_facts', []))}\n"
            f"SOURCE: {truncate(item.get('body', ''), 3000)}\nCONTEXT ENTRIES:\n{context_txt}"
        )
        out = structured_call(
            prompt,
            ExplainerOut,
            lambda h=draft.get("headline", ""), r=risk, t=tags: stub_explainer(h, r, t),
            errors=errors,
            agent="explainer",
        )
        draft["explainer"] = {s.value: getattr(out, s.value, "").strip() for s in ReaderSituation}

    return {"drafts": drafts, "errors": list(state.get("errors") or []) + errors}
