"""Small deterministic text helpers shared by the nodes (no LLM, no DB)."""

from __future__ import annotations

import hashlib
import html
import re
import unicodedata

from apps.common.choices import ReaderNeed, RiskTier

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ0-9\"“])")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_WORD_RE = re.compile(r"[\wåäöÅÄÖ-]+", re.UNICODE)


def clean_html(text: str) -> str:
    text = _TAG_RE.sub(" ", text or "")
    return _WS_RE.sub(" ", html.unescape(text)).strip()


def sentences(text: str) -> list[str]:
    text = _WS_RE.sub(" ", text or "").strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_RE.split(text) if s.strip()]


def truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD_RE.findall(text or "") if len(t) > 1]


def content_hash(title: str, body: str) -> str:
    return hashlib.sha256(f"{(title or '').strip()}\n{(body or '').strip()}".encode()).hexdigest()


def jaccard(a: str, b: str) -> float:
    sa, sb = set(tokens(a)), set(tokens(b))
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def normalize_digits(text: str) -> str:
    """Map any Unicode decimal digit (e.g. Arabic-Indic) to ASCII."""
    out = []
    for ch in text or "":
        if ch.isdigit() and not ("0" <= ch <= "9"):
            try:
                out.append(str(unicodedata.digit(ch)))
                continue
            except (TypeError, ValueError):
                pass
        out.append(ch)
    return "".join(out)


# --------------------------------------------------------------------------
# Risk / topic keyword heuristics (FR-3.7 fallback when the LLM is absent).
# Patterns are matched case-insensitively against title + body.
# --------------------------------------------------------------------------
RISK_KEYWORDS: dict[str, list[str]] = {
    RiskTier.HIGH: [
        r"oleskelulu[pv]", r"residence permit", r"\bmigri\b", r"maahanmuutto", r"turvapaik",
        r"tervey", r"\bhealth", r"sairaala", r"hospital", r"rokot", r"vaccin", r"epidemi",
        r"\btyö", r"employment", r"työlupa", r"work permit", r"te-palvel", r"tyött",
        r"\blaki\b", r"lain\b", r"oikeus", r"\blegal\b", r"court", r"tuomio", r"rikos",
        r"turvallisuu", r"\bsafety\b", r"vaara", r"varoitus", r"evakuo", r"poliisi", r"police",
        r"\bkela\b", r"verokort", r"tax card",
    ],
    RiskTier.MEDIUM: [
        r"liikenne", r"liikentee", r"bussi", r"\bbus\b", r"transport", r"juna", r"\btrain",
        r"palvelu", r"services?\b", r"tapahtum", r"\bevent", r"festivaal", r"konsert",
        r"koulu", r"school", r"kirjasto", r"library", r"tietyö", r"roadwork",
    ],
    RiskTier.LOW: [
        r"aukioloaj", r"opening hours", r"\bauki\b", r"\bsää", r"weather", r"lumi", r"pakkas",
        r"\bsnow\b",
    ],
}

TOPIC_TAGS: dict[str, list[str]] = {
    "immigration": [r"oleskelulu[pv]", r"residence permit", r"\bmigri\b", r"maahanmuutto"],
    "health": [r"tervey", r"\bhealth", r"sairaala", r"rokot", r"neuvola"],
    "work": [r"\btyö", r"employment", r"te-palvel", r"työpaik"],
    "legal": [r"\blaki\b", r"oikeus", r"\blegal\b", r"tuomio"],
    "safety": [r"turvallisuu", r"\bsafety\b", r"varoitus", r"poliisi", r"evakuo"],
    "transport": [r"liikenne", r"bussi", r"\bbus\b", r"juna", r"tietyö"],
    "services": [r"palvelu", r"kirjasto", r"\bkela\b", r"verokort", r"\bdvv\b"],
    "events": [r"tapahtum", r"\bevent", r"festivaal", r"konsert"],
    "education": [r"koulu", r"yliopisto", r"university", r"opiskel", r"student"],
    "weather": [r"\bsää", r"weather", r"lumi", r"pakkas"],
    "opening_hours": [r"aukioloaj", r"opening hours"],
    "housing": [r"asunto", r"vuokra", r"housing"],
}

# Things a newcomer needs in their first week (FR-3.11 arrival buckets).
FIRST_WEEK_PATTERNS = [r"oleskelulu[pv]", r"\bdvv\b", r"maistraat", r"henkilötunn", r"verokort", r"\bkela\b", r"pankkitil"]


def _matches(patterns: list[str], text: str) -> list[str]:
    low = (text or "").lower()
    return [p for p in patterns if re.search(p, low)]


def heuristic_risk(text: str) -> tuple[str, list[str]]:
    """Return (risk_tier, matched_patterns). Unknown topics default to MEDIUM
    (conservative: they still require editor review)."""
    for tier in (RiskTier.HIGH, RiskTier.MEDIUM, RiskTier.LOW):
        hits = _matches(RISK_KEYWORDS[tier], text)
        if hits:
            return str(tier.value), hits
    return str(RiskTier.MEDIUM.value), []


RISK_ORDER = {RiskTier.LOW.value: 0, RiskTier.MEDIUM.value: 1, RiskTier.HIGH.value: 2}


def max_risk(*tiers: str) -> str:
    valid = [t for t in tiers if t in RISK_ORDER]
    return max(valid, key=lambda t: RISK_ORDER[t]) if valid else RiskTier.MEDIUM.value


def topic_tags(text: str) -> list[str]:
    return [tag for tag, pats in TOPIC_TAGS.items() if _matches(pats, text)]


def heuristic_reader_needs(text: str, risk_tier: str, is_signal: bool = False, contribution_kind: str = "") -> list[str]:
    needs: list[str] = []
    tags = set(topic_tags(text))
    if risk_tier == RiskTier.HIGH.value or tags & {"services", "immigration", "work", "health"}:
        needs.append(ReaderNeed.USEFULNESS.value)
    if tags & {"legal", "immigration"} or contribution_kind == "question":
        needs.append(ReaderNeed.UNDERSTANDING.value)
    if tags & {"events"}:
        needs += [ReaderNeed.COMMUNITY.value, ReaderNeed.BREAK.value]
    if is_signal or contribution_kind == "bridge_story":
        needs.append(ReaderNeed.COMMUNITY.value)
    needs.append(ReaderNeed.INFORMATION.value)
    out: list[str] = []
    for n in needs:
        if n not in out:
            out.append(n)
    return out[:3]


def is_first_week_topic(text: str) -> bool:
    return bool(_matches(FIRST_WEEK_PATTERNS, text))


def hashing_embedding(text: str, dim: int = 64) -> list[float]:
    """Feature-hashing bag-of-words embedding (L2-normalised).

    TODO: replace with a real multilingual embedding model (e.g. Voyage /
    sentence-transformers) once the recommender needs semantic similarity.
    """
    vec = [0.0] * dim
    for tok in tokens(text):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h >> 8) & 1 else -1.0
    norm = sum(v * v for v in vec) ** 0.5
    return [round(v / norm, 6) for v in vec] if norm else vec
