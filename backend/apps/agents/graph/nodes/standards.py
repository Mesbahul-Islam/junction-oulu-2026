"""Standards agent - newsroom role: **standards desk / ethics check** (FR-3.13).

Human counterpart (FR-3.6): the standards editor, who gives final sign-off.
Runs the shared ``STANDARDS_CHECKLIST`` (imported from
``apps.editorial.services`` when available, local fallback otherwise) against
each draft. Items the machine can decide get ``pass``/``fail``; everything else
gets ``note: manual check`` for the human standards editor. The agent never
approves anything - a pass only means "nothing obviously wrong".
"""

from __future__ import annotations

import re
from typing import Any

from apps.editorial.checklist import detect as detect_sensitive

from ..state import NewsroomState
from ..text import classify_content

# Fallback if apps.editorial.services.STANDARDS_CHECKLIST is not defined.
LOCAL_STANDARDS_CHECKLIST: list[tuple[str, str]] = [
    ("source_attributed", "Every claim is attributed to a named, linked source"),
    ("facts_verified", "Dates, numbers and names verified against the source"),
    ("no_sensationalism", "Headline is neutral and not clickbait"),
    ("background_separated", "Background/context is labelled and kept apart from the news"),
    ("privacy_named_persons", "Private persons are named only with consent"),
    ("ai_disclosure", "AI involvement is disclosed to readers"),
    ("sami_human_translation", "Sámi versions are written by a human translator"),
    ("expiry_set", "Expiry / review date is set for time-sensitive info"),
    ("plain_language", "Plain language suitable for the audience"),
]


def get_checklist() -> list[tuple[str, str]]:
    STANDARDS_CHECKLIST = None
    for module in ("apps.editorial.services", "apps.editorial.models"):
        try:
            STANDARDS_CHECKLIST = getattr(__import__(module, fromlist=["STANDARDS_CHECKLIST"]), "STANDARDS_CHECKLIST")
            break
        except Exception:
            continue
    if not STANDARDS_CHECKLIST:
        return LOCAL_STANDARDS_CHECKLIST
    if isinstance(STANDARDS_CHECKLIST, dict):
        return [(str(k), str(v)) for k, v in STANDARDS_CHECKLIST.items()] or LOCAL_STANDARDS_CHECKLIST
    items: list[tuple[str, str]] = []
    for entry in STANDARDS_CHECKLIST:
        if isinstance(entry, (list, tuple)) and entry:
            items.append((str(entry[0]), str(entry[1]) if len(entry) > 1 else str(entry[0])))
        elif isinstance(entry, dict):
            k = entry.get("key") or entry.get("id") or entry.get("name")
            items.append((str(k), str(entry.get("label") or entry.get("description") or k)))
        else:
            items.append((str(entry), str(entry)))
    return items or LOCAL_STANDARDS_CHECKLIST


_CLICKBAIT = re.compile(r"!|uskomaton|järkyttä|shock|you won't believe|et usko", re.I)
_PERSON_NAME = re.compile(r"\b[A-ZÅÄÖ][a-zåäö]+ [A-ZÅÄÖ][a-zåäö]+\b")


def _auto_checks(key: str, state: NewsroomState) -> dict[str, str]:
    raw = {r["key"]: r for r in state.get("raw_items") or []}
    item = raw.get(key, {})
    draft = (state.get("drafts") or {}).get(key, {})
    assignment = (state.get("assignments") or {}).get(key, {})
    verification = (state.get("verification") or {}).get(key, {})
    translations = (state.get("translations") or {}).get(key, {})
    headline = draft.get("headline", "")
    is_signal = item.get("kind") == "community_signal"

    checks: dict[str, str] = {}
    checks["source_attributed"] = (
        "pass" if item.get("url") and item.get("publisher") else
        "fail" if is_signal else "note: source URL or publisher missing"
    )
    checks["facts_verified"] = "pass" if verification and all(v.get("passed") for v in verification.values()) else "fail"
    checks["no_sensationalism"] = "fail" if (_CLICKBAIT.search(headline) or (headline.isupper() and len(headline) > 8)) else "pass"
    background = draft.get("background", "")
    checks["background_separated"] = (
        "pass" if not background or (draft.get("background_label") and draft.get("background_context_ids") is not None) else "fail"
    )
    if is_signal and not item.get("named_persons_consent") and _PERSON_NAME.search(
        f"{headline} {draft.get('summary', '')}"
    ):
        checks["privacy_named_persons"] = "fail"
    else:
        checks["privacy_named_persons"] = "note: manual check" if not is_signal else "pass"
    # JSN 11 / 16: the source must be news, and nothing in the draft may read as opinion or advertising.
    draft_text = f"{headline}\n{draft.get('summary', '')}"
    source_type = item.get("content_type") or classify_content(item.get("title", ""), item.get("body", ""), item.get("url", ""))[0]
    draft_type = classify_content(headline, draft.get("summary", ""))[0]
    checks["fact_vs_opinion"] = "fail" if "opinion" in (source_type, draft_type) else "pass"
    checks["editorial_separated_from_ads"] = "fail" if "commercial" in (source_type, draft_type) else "pass"
    checks["ai_disclosure"] = "pass"  # Snippet.ai_generated=True drives the reader-facing disclosure
    sami = [lang for lang, v in translations.items() if v.get("needs_human_translation")]
    machine_sami = [
        lang for lang, v in translations.items()
        if v.get("needs_human_translation") is False and lang in {"se", "smn", "sms"}
    ]
    checks["sami_human_translation"] = (
        "fail" if machine_sami else (f"note: awaiting human translation ({', '.join(sami)})" if sami else "pass")
    )
    checks["expiry_set"] = "pass" if assignment.get("expires_at") else "fail"
    checks["plain_language"] = "pass" if len(draft.get("summary", "")) <= 600 else "note: summary long, simplify"
    return checks


# Editorial checklist item names -> the automatic check that answers them.
ALIASES = {
    "sources_named": "source_attributed",
    "ai_role_disclosed": "ai_disclosure",
    "privacy_of_named_persons": "privacy_named_persons",
}
# Structural guarantees of the platform for agent-made snippets.
PLATFORM_GUARANTEES = {
    "correction_path": "pass",  # report button + public corrections log (editorial.Correction)
}


def standards(state: NewsroomState) -> dict[str, Any]:
    checklist = get_checklist()
    results: dict[str, dict] = {}
    for key in (state.get("drafts") or {}):
        auto = _auto_checks(key, state)
        res: dict[str, str] = {}
        for item, _label in checklist:
            res[item] = auto.get(ALIASES.get(item, item)) or PLATFORM_GUARANTEES.get(item) or "note: manual check"
        # Extra agent checks not on the editorial checklist are reported too.
        used = {ALIASES.get(item, item) for item, _ in checklist}
        res.update({k: v for k, v in auto.items() if k not in used})
        # Sensitive topics (crime, right of reply, minors, illness/death): not a failure, but an
        # editor must confirm each one before publishing (editorial.ChecklistItem).
        item = next((r for r in state.get("raw_items") or [] if r.get("key") == key), {})
        draft = state["drafts"][key]
        text = " ".join([item.get("title", ""), item.get("body", ""), draft.get("headline", ""), draft.get("summary", "")])
        results[key] = {"results": res, "passed": not any(v == "fail" for v in res.values()), "sensitive": detect_sensitive(text)}
    return {"standards": results}
