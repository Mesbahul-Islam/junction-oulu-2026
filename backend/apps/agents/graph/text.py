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
# Patterns are matched case-insensitively against title + body; the first tier
# (high, then low, then medium) with a hit wins, no hit means medium.
# --------------------------------------------------------------------------
RISK_KEYWORDS: dict[str, list[str]] = {
    # Only terms that clearly concern a reader's permits, benefits, health care,
    # employment services or an official safety instruction (FR-3.7). Broad words
    # ("työ", "oikeus", "poliisi") are left out: they match ordinary news, and this
    # list also acts as a floor the LLM's tier can't go below.
    RiskTier.HIGH: [
        r"oleskelulu[pv]", r"residence permit", r"\bmigri\b", r"maahanmuuttovira", r"turvapaik",
        r"\bkela\b", r"kelan\b", r"verokort", r"tax card", r"verohallin",
        r"te-palvel", r"työlupa", r"work permit", r"työttömyysturv", r"työttömyysetuu",
        r"terveyskesk", r"terveysasem", r"päivystys", r"rokotu", r"vaccin", r"epidemi",
        r"hätätiedot", r"vaaratiedot", r"evakuo", r"keittokehot", r"boil.water",
    ],
    RiskTier.MEDIUM: [
        r"liikenne", r"liikentee", r"bussi", r"\bbus\b", r"transport", r"juna", r"\btrain",
        r"palvelu", r"services?\b", r"tapahtum", r"\bevent", r"festivaal", r"konsert",
        r"koulu", r"school", r"kirjasto", r"library", r"tietyö", r"roadwork", r"\bkeli", r"liukas",
        r"jäte", r"sähkökatko", r"vesikatko",
    ],
    RiskTier.LOW: [
        r"aukioloaj", r"opening hours", r"\bauki\b", r"\bsää\b", r"weather", r"lumi", r"pakkas",
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
    "sports": [r"urheilu", r"jääkiekko", r"\bliiga", r"kärpät", r"jalkapallo", r"futis", r"\bottelu", r"sport"],
    "culture": [r"kulttuuri", r"teatteri", r"museo", r"näyttely", r"elokuva", r"kirjailij", r"\btaide", r"culture"],
}

# Things a newcomer needs in their first week (FR-3.11 arrival buckets).
FIRST_WEEK_PATTERNS = [r"oleskelulu[pv]", r"\bdvv\b", r"maistraat", r"henkilötunn", r"verokort", r"\bkela\b", r"pankkitil"]


def _matches(patterns: list[str], text: str) -> list[str]:
    low = (text or "").lower()
    return [p for p in patterns if re.search(p, low)]


def heuristic_risk(text: str) -> tuple[str, list[str]]:
    """Return (risk_tier, matched_patterns). Unknown topics default to MEDIUM
    (conservative: they still require editor review)."""
    for tier in (RiskTier.HIGH, RiskTier.LOW, RiskTier.MEDIUM):  # low terms are the most specific
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


# --------------------------------------------------------------------------
# Language check for translations (fact-checker): is the text really in the
# language it is filed under? Deterministic, so a confused model can't vouch for itself.
# --------------------------------------------------------------------------
_SCRIPTS = {
    "arabic": re.compile(r"[؀-ۿݐ-ݿ]"),
    "cyrillic": re.compile(r"[Ѐ-ӿ]"),
    "latin": re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿŠšŽžÕõ]"),
}
EXPECTED_SCRIPT = {"ar": "arabic", "uk": "cyrillic", "ru": "cyrillic"}  # everything else: latin
_UK_ONLY, _RU_ONLY = set("іїєґІЇЄҐ"), set("ыэъёЫЭЪЁ")
STOPWORDS = {
    "en": {"the", "and", "of", "to", "in", "for", "is", "are", "was", "with", "on", "that", "this", "by", "from", "has", "have", "will", "at"},
    "sv": {"och", "att", "det", "som", "ett", "för", "är", "på", "med", "av", "till", "den", "har", "inte", "om", "var", "från", "efter", "vid"},
    "fi": {"ja", "on", "ei", "että", "oli", "ovat", "mutta", "kun", "tai", "myös", "joka", "hän", "tämä", "sen", "kanssa", "mukaan", "jälkeen"},
    "et": {"ja", "on", "ei", "see", "et", "oli", "mis", "ka", "kui", "aga", "või", "oma", "ning", "seda", "pärast", "mitte", "kes"},
    "so": {"iyo", "oo", "ku", "ka", "waa", "ah", "la", "uu", "ay", "lagu", "ayaa", "kale", "sida", "waxa"},
}
LANGUAGE_LABELS = {"en": "English", "sv": "Swedish", "fi": "Finnish", "et": "Estonian", "so": "Somali",
                   "uk": "Ukrainian", "ru": "Russian", "ar": "Arabic"}


def language_problem(text: str, lang: str) -> str | None:
    """Why ``text`` doesn't look like language ``lang``, or None if it does (or can't tell)."""
    counts = {name: len(rx.findall(text or "")) for name, rx in _SCRIPTS.items()}
    if sum(counts.values()) < 20:
        return None  # too little text to judge
    script = max(counts, key=counts.get)
    expected = EXPECTED_SCRIPT.get(lang, "latin")
    name = LANGUAGE_LABELS.get(lang, lang)
    if script != expected:
        return f"text is mostly in {script} script, not {expected} as {name} should be"
    if lang in ("uk", "ru"):
        uk, ru = sum(c in _UK_ONLY for c in text), sum(c in _RU_ONLY for c in text)
        if lang == "uk" and ru > uk:
            return "text looks Russian (ы, э, ъ, ё), not Ukrainian"
        if lang == "ru" and uk > ru:
            return "text looks Ukrainian (і, ї, є, ґ), not Russian"
        return None
    if lang in STOPWORDS:
        words = re.findall(r"[a-zåäöõüšž]+", text.lower())
        scores = {code: sum(w in sw for w in words) for code, sw in STOPWORDS.items()}
        best = max(scores, key=scores.get)
        if best != lang and scores[best] >= 2 and scores[best] > 2 * scores[lang]:
            return f"text looks {LANGUAGE_LABELS[best]}, not {name}"
    return None


# --------------------------------------------------------------------------
# Name matching across Finnish inflection (fact-checker): "Oulussa" (in Oulu),
# "Oulun" (Oulu's) and "Raksilassa" refer to Oulu / Raksila, and "Kärpille" to Kärpät.
# --------------------------------------------------------------------------
# Case endings, longest first; stripping one yields candidate base forms.
_FI_ENDINGS = (
    "ineen", "ssa", "ssä", "sta", "stä", "lla", "llä", "lta", "ltä", "lle", "ksi", "tta", "ttä", "hin",
    "na", "nä", "ta", "tä", "an", "än", "en", "in", "on", "un", "yn", "n", "a", "ä", "t",
)


def name_stems(name: str) -> set[str]:
    """The name in lower case plus its forms with one Finnish case ending removed (min. 3 letters left)."""
    low = name.lower()
    return {low} | {low[: -len(e)] for e in _FI_ENDINGS if low.endswith(e) and len(low) - len(e) >= 3}


def _common_prefix(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def name_matches(name: str, candidates) -> bool:
    """Is ``name`` (possibly inflected) one of ``candidates`` (words, possibly inflected)?

    Both sides are reduced to stems. Two stems match if equal, or if they agree apart
    from a short ending (consonant gradation such as Kärpät/Kärpille, Tampere/Tampereella).
    A merely longer word doesn't count ("Oulu" is not "Oulunsalo"); names under 4 letters
    only match exactly or with a case ending ("TPS", "TPSn").
    """
    stems = name_stems(name)
    for cand in candidates:
        for a in stems:
            for b in name_stems(cand):
                if a == b:
                    return True
                shared = _common_prefix(a, b)
                if shared >= max(4, min(len(a), len(b)) - 1) and max(len(a), len(b)) - shared <= 3:
                    return True
    return False


def guess_language(text: str) -> str:
    """Best guess of the language of a short text ("" if unsure), for community posts."""
    counts = {name: len(rx.findall(text or "")) for name, rx in _SCRIPTS.items()}
    if sum(counts.values()) < 8:
        return ""
    script = max(counts, key=counts.get)
    if script == "arabic":
        return "ar"
    if script == "cyrillic":
        return "uk" if sum(c in _UK_ONLY for c in text) >= sum(c in _RU_ONLY for c in text) else "ru"
    low = (text or "").lower()
    words = re.findall(r"[a-zåäöõüšž]+", low)
    scores = {code: sum(w in sw for w in words) for code, sw in STOPWORDS.items()}
    # Letters only break ties between Latin-script languages: å Swedish, õ Estonian, ä/ö Finnish.
    if "å" in low:
        scores["sv"] += 0.5
    elif "õ" in low:
        scores["et"] += 0.5
    elif re.search(r"[äö]", low):
        scores["fi"] += 0.5
    best = max(scores, key=scores.get)
    return best if scores[best] >= 1 else ""
