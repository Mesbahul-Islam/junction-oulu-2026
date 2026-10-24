"""Sensitive-story checklist (JSN Journalist's Guidelines, https://jsn.fi/en/journalists-guidelines/).

When a story touches one of these topics, an editor must explicitly confirm each item
before the snippet can be approved or published (see services.approve / can_publish).
Detection is a deliberately broad keyword match on the source and the draft (Finnish and
English): a false alarm costs the editor one tick, a miss can harm a real person.
"""

import re

SENSITIVE_CHECKS = {
    "crime": {
        "label": "Crime or suspicion: no suspect or accused is identified unless clearly justified, "
        "and guilt is not presumed before a court decides.",
        "clauses": "30–32",
        "patterns": [
            r"epäil", r"\brikos", r"poliisi", r"syyte", r"syytet", r"tuomi", r"pidätet", r"vangit", r"esitutkin",
            r"oikeudenkäyn", r"käräjä", r"tutkintapyyn", r"kavallu", r"murha", r"pahoinpitel", r"varkau",
            r"\bsuspect", r"\barrest", r"\bcharged\b", r"\bconvicted\b", r"\bpolice\b", r"\bcrime",
        ],
    },
    "right_of_reply": {
        "label": "A person or organisation is shown in a very negative light: they were given a chance "
        "to respond, or the story says they were asked.",
        "clauses": "21–22",
        "patterns": [
            r"sakko", r"sakott", r"potku", r"irtisan", r"erotet", r"kavallu", r"väärinkäyt", r"kohu", r"skandaali",
            r"\brikkoi", r"rikkom", r"syyte", r"epäil", r"\bfined\b", r"\bfired\b", r"\bscandal", r"\baccused\b",
        ],
    },
    "minors": {
        "label": "Children or young people: no minor or otherwise vulnerable person is identifiable.",
        "clauses": "27, 32",
        "patterns": [
            r"\blapsi", r"\blapse", r"alaikäi", r"\bnuori\b", r"\bnuoret\b", r"koululai", r"oppila",
            r"\b(1[0-7]|[1-9])-vuotia", r"\bchild", r"\bminor\b", r"\bteen", r"\bpupil",
        ],
    },
    "personal_sensitive": {
        "label": "Illness, death, accidents or victims: handled with discretion, with no identifying "
        "details without consent.",
        "clauses": "25, 28, 33",
        "patterns": [
            r"kuoli", r"kuolema", r"menehty", r"onnettomuu", r"loukkaant", r"sairau", r"sairast", r"itsemurh",
            r"\buhri", r"seksuaali", r"\bdied\b", r"\bdeath", r"\baccident", r"\binjur", r"\bvictim", r"\billness",
            r"\bsuicide",
        ],
    },
}


def detect(text: str) -> list[str]:
    """Checklist keys whose topic appears in ``text`` (empty if none)."""
    low = (text or "").lower()
    return [key for key, check in SENSITIVE_CHECKS.items() if any(re.search(p, low) for p in check["patterns"])]
