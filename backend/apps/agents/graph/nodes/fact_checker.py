"""Fact-checker agent - newsroom role: **verification desk** (FR-3.2, FR-3.13).

Human counterpart (FR-3.6): the editor who resolves the flags it raises.
Deterministic checks first, LLM second:

1. Regex-extract dates, clock times, numbers and proper names from the source
   and from every language version; the Finnish draft may not contain facts
   absent from the source, and each translation must carry exactly the draft's
   dates/times/numbers (names are compared for Latin-script languages only).
2. Back-translation: each translation is translated back to Finnish (LLM) and
   compared with the draft.
3. A confidence score per language; the item's confidence is the minimum.

Results go to ``state["verification"][key][lang]`` and become
``editorial.VerificationResult`` rows. Sámi placeholders are not checked
(there is no text yet - a human translator writes it).
"""

from __future__ import annotations

import re
from typing import Any

from apps.common.choices import SOURCE_LANGUAGE

from ..llm import language_chunks, structured_call
from ..schemas import BackTranslationOut, BackTranslationsOut, LanguageBackTranslation
from ..state import NewsroomState
from ..text import jaccard, normalize_digits, truncate

_FULL_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_SHORT_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(?!\d)")
_ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_TIME_RE = re.compile(r"\b(\d{1,2})[.:](\d{2})\b")
_NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")
_NAME_RE = re.compile(r"(?<![.!?]\s)(?<!^)\b([A-ZÅÄÖ][a-zåäöéü]+(?:-[A-ZÅÄÖ][a-zåäö]+)?|[A-ZÅÄÖ]{2,})\b")
_LANG_PREFIX_RE = re.compile(r"\[[a-z]{2,3}\]\s*")

LATIN_SCRIPT = {"fi", "sv", "en", "et", "so", "se", "smn", "sms"}
ERROR_PENALTY = 0.2
WARNING_PENALTY = 0.05


def _threshold() -> float:
    try:
        from django.conf import settings

        return float(getattr(settings, "AGENT_CONFIDENCE_THRESHOLD", 0.7))
    except Exception:  # settings not configured
        return 0.7


def extract_facts(text: str) -> dict[str, set[str]]:
    """Return {"dates", "times", "numbers", "names"} sets of normalised strings."""
    text = normalize_digits(text or "")
    dates: set[str] = set()
    times: set[str] = set()

    def _date(m):
        d, mth = int(m.group(1)), int(m.group(2))
        if not (1 <= d <= 31 and 1 <= mth <= 12):
            return m.group(0)
        y = m.group(3) if m.lastindex and m.lastindex >= 3 else ""
        dates.add(f"{d}.{mth}." + (y or ""))
        return " "

    def _iso(m):
        dates.add(f"{int(m.group(3))}.{int(m.group(2))}.{m.group(1)}")
        return " "

    def _time(m):
        h, mi = int(m.group(1)), int(m.group(2))
        if h < 24 and mi < 60:
            times.add(f"{h}:{mi:02d}")
            return " "
        return m.group(0)

    # Order matters: full dates, then clock times, then short "1.12." dates.
    rest = _ISO_DATE_RE.sub(_iso, text)
    rest = _FULL_DATE_RE.sub(_date, rest)
    rest = _TIME_RE.sub(_time, rest)
    rest = _SHORT_DATE_RE.sub(_date, rest)
    numbers = {_norm_num(n) for n in _NUM_RE.findall(rest)}
    names = set()
    for line in re.split(r"[\n•;]", text):
        names |= {n for n in _NAME_RE.findall(line.strip())}
    return {"dates": dates, "times": times, "numbers": numbers, "names": names}


def _norm_num(n: str) -> str:
    n = n.replace(",", ".")
    if "." in n:
        n = n.rstrip("0").rstrip(".")
    return n.lstrip("0") or "0"


def _date_key(d: str) -> str:
    """Compare dates on day.month (a translation may drop the year)."""
    parts = d.split(".")
    return ".".join(parts[:2])


def compare_facts(reference: dict, candidate: dict, *, language: str, check_names: bool, glossary_terms=()) -> list[dict]:
    """Mismatches between the reference (draft) facts and a candidate version."""
    out: list[dict] = []
    ref_dates = {_date_key(d) for d in reference["dates"]}
    cand_dates = {_date_key(d) for d in candidate["dates"]}
    for kind, ref, cand in (
        ("date", ref_dates, cand_dates),
        ("time", reference["times"], candidate["times"]),
        ("number", reference["numbers"], candidate["numbers"]),
    ):
        for v in sorted(ref - cand):
            out.append({"language": language, "kind": kind, "value": v, "issue": "missing_in_translation", "severity": "error"})
        for v in sorted(cand - ref):
            out.append({"language": language, "kind": kind, "value": v, "issue": "not_in_original", "severity": "error"})
    if check_names:
        skip = {t.lower() for t in glossary_terms}
        cand_low = {n.lower() for n in candidate["names"]}
        for name in sorted(reference["names"]):
            if name.lower() in skip or name.lower() in cand_low:
                continue
            out.append({"language": language, "kind": "name", "value": name, "issue": "missing_in_translation", "severity": "warning"})
    return out


def _version_text(v: dict) -> str:
    return "\n".join([v.get("headline", ""), v.get("summary", ""), *v.get("key_facts", [])])


def check_draft_against_source(draft: dict, source_text: str) -> list[dict]:
    lang = draft.get("language", SOURCE_LANGUAGE.value)
    d, s = extract_facts(_version_text(draft)), extract_facts(source_text)
    out: list[dict] = []
    src_dates = {_date_key(x) for x in s["dates"]}
    for v in sorted({_date_key(x) for x in d["dates"]} - src_dates):
        out.append({"language": lang, "kind": "date", "value": v, "issue": "not_in_source", "severity": "error"})
    for kind in ("times", "numbers"):
        for v in sorted(d[kind] - s[kind]):
            out.append({"language": lang, "kind": kind[:-1], "value": v, "issue": "not_in_source", "severity": "error"})
    src_low = source_text.lower()
    for name in sorted(d["names"]):
        if name.lower() not in src_low:
            out.append({"language": lang, "kind": "name", "value": name, "issue": "not_in_source", "severity": "warning"})
    return out


def _confidence(base: float, mismatches: list[dict]) -> float:
    errors = sum(1 for m in mismatches if m.get("severity") == "error")
    warnings = sum(1 for m in mismatches if m.get("severity") != "error")
    return round(max(0.0, min(1.0, base - ERROR_PENALTY * errors - WARNING_PENALTY * warnings)), 3)


def stub_back_translation(version: dict, draft: dict) -> BackTranslationOut:
    back = _LANG_PREFIX_RE.sub("", version.get("summary", ""))
    sim = jaccard(back, draft.get("summary", ""))
    return BackTranslationOut(back_translation=back, meaning_preserved=sim >= 0.6, similarity=round(sim, 3), issues=[])


def back_translate_all(draft: dict, versions: dict[str, dict], errors: list) -> dict[str, BackTranslationOut]:
    """Back-translate every language version of one story with ONE LLM call."""
    blocks = "\n\n".join(f"TRANSLATION ({lang}):\n{truncate(_version_text(v), 2500)}" for lang, v in versions.items())
    prompt = (
        "For each translation below: translate it back into Finnish, then compare it with the Finnish "
        "original. Return one check per language code, with similarity 0-1, whether meaning is preserved, "
        "and concrete issues (changed numbers, dates, names, negations, missing or added claims).\n\n"
        f"FINNISH ORIGINAL:\n{_version_text(draft)}\n\n{blocks}"
    )

    def fallback():
        return BackTranslationsOut(checks=[
            LanguageBackTranslation(language=lang, **stub_back_translation(v, draft).model_dump()) for lang, v in versions.items()
        ])

    out = structured_call(prompt, BackTranslationsOut, fallback, errors=errors, agent="fact_checker")
    got = {c.language.strip().lower(): c for c in out.checks}
    result = {}
    for lang, v in versions.items():
        if lang not in got:
            errors.append({"agent": "fact_checker", "error": f"no back-translation for {lang}, used fallback"})
        result[lang] = got.get(lang) or stub_back_translation(v, draft)
    return result


def fact_checker(state: NewsroomState) -> dict[str, Any]:
    errors: list[dict] = []
    raw = {r["key"]: r for r in state.get("raw_items") or []}
    glossary = state.get("glossary") or []
    threshold = _threshold()
    verification: dict[str, dict[str, dict]] = {}
    confidence: dict[str, float] = {}

    for key, draft in (state.get("drafts") or {}).items():
        item = raw.get(key, {})
        src_lang = draft.get("language", SOURCE_LANGUAGE.value)
        source_text = f"{item.get('title', '')}\n{item.get('body', '')}"
        per_lang: dict[str, dict] = {}

        # 1) Finnish draft vs source
        mism = check_draft_against_source(draft, source_text)
        if item.get("kind") == "community_signal":
            mism.append({
                "language": src_lang, "kind": "source", "value": item.get("key"),
                "issue": "no_official_source: community tip, verify independently", "severity": "error",
            })
        conf = _confidence(1.0, mism)
        per_lang[src_lang] = {
            "passed": not any(m["severity"] == "error" for m in mism) and conf >= threshold,
            "confidence": conf,
            "mismatches": mism,
            "back_translation": "",
        }

        # 2) each machine translation vs draft: deterministic fact check per language,
        #    then ONE back-translation call covering every language of this story.
        ref = extract_facts(_version_text(draft))
        checked = {}
        for lang, version in (state.get("translations") or {}).get(key, {}).items():
            if version.get("needs_human_translation"):
                continue  # Sámi placeholder: nothing to verify yet
            cand = extract_facts(_LANG_PREFIX_RE.sub("", _version_text(version)))
            terms = [g["term_fi"] for g in glossary if g.get("language") == lang]
            checked[lang] = (version, compare_facts(ref, cand, language=lang, check_names=lang in LATIN_SCRIPT, glossary_terms=terms))

        back = {}
        for chunk in language_chunks(list(checked)) if checked else []:
            back.update(back_translate_all(draft, {lang: checked[lang][0] for lang in chunk}, errors))
        for lang, (version, mism) in checked.items():
            bt = back[lang]
            for issue in bt.issues:
                mism.append({"language": lang, "kind": "meaning", "value": "", "issue": issue, "severity": "warning"})
            if not bt.meaning_preserved:
                mism.append({"language": lang, "kind": "meaning", "value": "", "issue": "back_translation_meaning_differs", "severity": "error"})
            conf = _confidence(max(0.0, min(1.0, float(bt.similarity))), mism)
            per_lang[lang] = {
                "passed": not any(m["severity"] == "error" for m in mism) and conf >= threshold,
                "confidence": conf,
                "mismatches": mism,
                "back_translation": bt.back_translation,
            }

        verification[key] = per_lang
        confidence[key] = min(v["confidence"] for v in per_lang.values()) if per_lang else 0.0

    return {"verification": verification, "confidence": confidence, "errors": list(state.get("errors") or []) + errors}
