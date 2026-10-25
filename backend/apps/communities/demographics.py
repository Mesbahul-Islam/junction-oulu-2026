"""Town demographics from Statistics Finland's open StatFin database (PxWeb API, no key).

Only public, aggregate figures per municipality, never anything about a person:
population and age groups, languages spoken, students, and tourist accommodation (a sign
of seasonal work). Jev gets them as part of the town's readership (``news_editor.audience``).

Where the figures live:
    data/municipalities.json   a snapshot of every municipality, checked into the repo.
                               ``bootstrap`` and the admin fill each geographic community's
                               ``demographics`` from it, with no network needed.
    CommunityGroup.demographics  what the newsroom reads on every run.
The figures change once a year. When Statistics Finland publishes a new year, run
``manage.py fetch_demographics --snapshot`` (about 5 requests for all of Finland), commit
the file, then ``manage.py fetch_demographics`` to update the communities from it.

What the statistics leave out: they count people with a municipality of residence, so
people on temporary protection (most Ukrainians who came after 2022) and most seasonal
workers are not in them. ``town_facts`` says so to Jev.

Tables (https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/):
    vaerak/11ra  key figures on population by area
    vaerak/11rm  language by municipality
    tyokay/115b  population by main type of activity (students)
    matk/117s    accommodation establishment capacity by municipality

Variable codes carry the classification date (``alue_23_20260101``) and change when
Statistics Finland updates its regional division, so they are looked up from each table's
metadata by prefix instead of being written here.
"""

from __future__ import annotations

import functools
import itertools
import json
import logging
import time
from pathlib import Path

import httpx
from django.utils import timezone

logger = logging.getLogger(__name__)

API = "https://pxdata.stat.fi/PxWeb/api/v1/en/StatFin"
SOURCE = "Statistics Finland, StatFin"
SNAPSHOT = Path(__file__).parent / "data" / "municipalities.json"
TIMEOUT = 60
RETRIES, RETRY_WAIT = 3, 10.0  # seconds; StatFin's limit window is 10 s
TOP_LANGUAGES = 8

KEY_FIGURES = {
    "vaerak-vaesto": "total",
    "vaesto_alle15_p": "under_15_pct",
    "vaesto_15_64_p": "age_15_64_pct",
    "vaesto_yli64_p": "over_64_pct",
    "vaesto_kieli_fi_p": "finnish_pct",
    "vaesto_kieli_sv_p": "swedish_pct",
    "vaesto_kieli_se": "sami_speakers",
    "vaesto_kieli_ulk_p": "foreign_language_pct",
    "vaesto_tausta_ulk_p": "foreign_background_pct",
}


class DemographicsError(Exception):
    pass


def _request(method: str, path: str, **kwargs) -> dict:
    """StatFin allows about 30 requests per 10 seconds; on 429 wait and try again."""
    for attempt in range(RETRIES + 1):
        resp = httpx.request(method, f"{API}/{path}", timeout=TIMEOUT, **kwargs)
        if resp.status_code != 429 or attempt == RETRIES:
            resp.raise_for_status()
            return resp.json()
        time.sleep(float(resp.headers.get("Retry-After") or RETRY_WAIT))
    raise AssertionError("unreachable")


@functools.lru_cache(maxsize=16)
def _metadata(path: str) -> tuple:
    """A table's variables. Cached for the process: they change only when Statistics Finland
    publishes a new year or regional division."""
    return tuple(_request("GET", path)["variables"])


class Table:
    """One StatFin table: its variables (looked up by prefix) and its latest final year."""

    def __init__(self, path: str):
        self.path = path
        self.variables = {v["code"]: v for v in _metadata(path)}

    def code(self, prefix: str) -> str:
        for code in self.variables:
            if code.startswith(prefix):
                return code
        raise DemographicsError(f"{self.path} has no variable starting with {prefix!r}")

    def labels(self, prefix: str) -> dict[str, str]:
        v = self.variables[self.code(prefix)]
        return dict(zip(v["values"], v["valueTexts"]))

    def latest_year(self) -> str:
        """The last year that isn't preliminary (preliminary years are labelled e.g. "2026*")."""
        final = [code for code, text in self.labels("timeperiod").items() if not text.endswith("*")]
        return final[-1] if final else list(self.labels("timeperiod"))[-1]

    def query(self, **selections) -> list[tuple[dict, float | None]]:
        """Select values per variable (a code, a list of codes, or "*" for all). Returns one
        ({prefix: category code}, value) row per cell."""
        codes = {prefix: self.code(prefix) for prefix in selections}
        query = []
        for prefix, values in selections.items():
            if values == "*":
                query.append({"code": codes[prefix], "selection": {"filter": "all", "values": ["*"]}})
            else:
                values = values if isinstance(values, list) else [values]
                query.append({"code": codes[prefix], "selection": {"filter": "item", "values": values}})
        data = _request("POST", self.path, json={"query": query, "response": {"format": "json-stat2"}})
        prefix_of = {code: prefix for prefix, code in codes.items()}
        orders = []
        for dim in data["id"]:
            index = data["dimension"][dim]["category"]["index"]
            orders.append(sorted(index, key=index.get))
        return [({prefix_of.get(dim, dim): cat for dim, cat in zip(data["id"], combo)}, value)
                for combo, value in zip(itertools.product(*orders), data["value"])]


def _areas(table: Table, prefix: str, codes: list[str] | None, ku: bool) -> list[str] | str:
    """Area selection for municipality codes ("564"), or every municipality when codes is None."""
    if codes is not None:
        return [f"KU{c}" if ku else c for c in codes]
    labels = table.labels(prefix)
    return [a for a in labels if (a.startswith("KU") if ku else a.isdigit())]


def _municipality(area: str) -> str:
    return area[2:] if area.startswith("KU") else area


# --- One function per table; each returns {municipality code: figures} ---------------------


def _population(codes):
    table = Table("vaerak/11ra.px")
    year = table.latest_year()
    names = table.labels("alue")
    out = {}
    for row, value in table.query(alue=_areas(table, "alue", codes, ku=True), contentscode=list(KEY_FIGURES),
                                  timeperiod=year):
        rec = out.setdefault(_municipality(row["alue"]), {"year": int(year), "name": names[row["alue"]].strip()})
        if value is not None:
            rec[KEY_FIGURES[row["contentscode"]]] = value
    return out


def _languages(codes):
    table = Table("vaerak/11rm.px")
    year = table.latest_year()
    labels = table.labels("kieli")
    counts: dict[str, dict[str, float]] = {}
    for row, value in table.query(alue=_areas(table, "alue", codes, ku=True), kieli="*", sukupuoli="SSS",
                                  timeperiod=year):
        counts.setdefault(_municipality(row["alue"]), {})[row["kieli"]] = value or 0
    out = {}
    for code, langs in counts.items():
        total = langs.get("SSS") or 0
        # Two-letter codes are languages; the rest are totals ("01", "02") and "other" ("98", "99").
        foreign = sorted(((n, c) for c, n in langs.items() if len(c) == 2 and c.isalpha() and c not in ("fi", "sv", "se")),
                         reverse=True)
        out[code] = {"year": int(year), "top_foreign": [
            {"code": c, "name": labels[c], "speakers": n, "pct": round(100 * n / total, 2) if total else None}
            for n, c in foreign[:TOP_LANGUAGES] if n]}
    return out


def _students(codes):
    table = Table("tyokay/115b.px")
    year = table.latest_year()
    rows = table.query(alue=_areas(table, "alue", codes, ku=True), paaasial="22", sukupuoli="SSS", ikaryhma="SSS",
                       timeperiod=year)
    # Students and pupils aged 15 or over.
    return {_municipality(row["alue"]): {"year": int(year), "count": value} for row, value in rows if value is not None}


def _tourism(codes):
    table = Table("matk/117s.px")
    year = table.latest_year()
    rows = table.query(kunta=_areas(table, "kunta", codes, ku=False), majoitus="01", contentscode="vuoteet",
                       timeperiod=year)
    return {row["kunta"]: {"year": int(year), "bed_places": value or 0} for row, value in rows}


SECTIONS = {"population": _population, "languages": _languages, "students": _students, "tourism": _tourism}


def build(codes: list[str] | None = None) -> dict[str, dict]:
    """Figures for these municipality codes, or every municipality when codes is None: one
    request per table. A table that fails is left out and named in each record's ``errors``."""
    parts, errors = {}, []
    for name, part in SECTIONS.items():
        try:
            parts[name] = part(codes)
        except (httpx.HTTPError, DemographicsError, KeyError, IndexError, ValueError) as exc:
            logger.warning("Statistics Finland %s failed: %s", name, exc)
            errors.append(f"{name}: {type(exc).__name__}")
    fetched_at = timezone.now().isoformat()
    out = {}
    for code, population in parts.get("population", {}).items():
        rec = {"source": SOURCE, "municipality_code": code, "municipality": population.pop("name"),
               "fetched_at": fetched_at, "errors": errors, "population": population}
        for name in ("languages", "students", "tourism"):
            if code in parts.get(name, {}):
                rec[name] = parts[name][code]
        total = population.get("total")
        if total and "students" in rec:
            rec["students"]["pct"] = round(100 * rec["students"]["count"] / total, 1)
        if total and "tourism" in rec:
            rec["tourism"]["beds_per_1000_residents"] = round(1000 * rec["tourism"]["bed_places"] / total, 1)
        out[code] = rec
    return out


def fetch(code: str) -> dict:
    """Live figures for one municipality, by its three-digit code."""
    rec = build([code]).get(code)
    if rec is None:
        raise DemographicsError(f"Statistics Finland returned nothing for municipality {code}")
    return rec


def municipality_code(name: str) -> str:
    """Statistics Finland's three-digit municipality code for a name ("Oulu" -> "564"), from
    the snapshot if there is one, else from the live table."""
    wanted = name.strip().lower()
    for code, rec in load_snapshot().items():
        if rec["municipality"].lower() == wanted:
            return code
    for area, label in Table("vaerak/11ra.px").labels("alue").items():
        if area.startswith("KU") and label.strip().lower() == wanted:
            return area[2:]
    raise DemographicsError(f"No municipality called {name!r} in Statistics Finland's data")


# --- The static snapshot --------------------------------------------------------------------


def write_snapshot() -> int:
    """Fetch every municipality and write data/municipalities.json. Returns how many."""
    records = build(None)
    if not records:
        raise DemographicsError("Statistics Finland returned no municipalities; the snapshot was not changed")
    SNAPSHOT.parent.mkdir(exist_ok=True)
    payload = {"source": SOURCE, "url": "https://pxdata.stat.fi/PxWeb/pxweb/en/StatFin/",
               "tables": ["vaerak/11ra", "vaerak/11rm", "tyokay/115b", "matk/117s"],
               "fetched_at": timezone.now().isoformat(), "municipalities": dict(sorted(records.items()))}
    SNAPSHOT.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    load_snapshot.cache_clear()
    return len(records)


@functools.lru_cache(maxsize=1)
def load_snapshot() -> dict[str, dict]:
    """{municipality code: figures} from the checked-in snapshot; empty if there is none."""
    try:
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))["municipalities"]
    except FileNotFoundError:
        return {}


def refresh(community, live: bool = False) -> dict:
    """Store the figures for a geographic community: from the snapshot, or from Statistics
    Finland when ``live``. Looks up its municipality code from ``community.municipality``."""
    if not community.municipality_code:
        if not community.municipality:
            raise DemographicsError(f"{community} has no municipality set")
        community.municipality_code = municipality_code(community.municipality)
    if live:
        data = fetch(community.municipality_code)
    else:
        data = load_snapshot().get(community.municipality_code)
        if data is None:
            raise DemographicsError(f"Municipality {community.municipality_code} is not in {SNAPSHOT.name}")
    community.demographics = data
    community.save(update_fields=["municipality_code", "demographics", "updated_at"])
    return data


def fill_missing() -> int:
    """Give every active geographic community without figures its snapshot figures (bootstrap)."""
    from .models import CommunityGroup

    filled = 0
    for group in CommunityGroup.objects.filter(kind=CommunityGroup.Kind.GEO, is_active=True, demographics={}):
        if not group.municipality:
            continue
        try:
            refresh(group)
            filled += 1
        except DemographicsError as exc:
            logger.warning("No demographics for %s: %s", group, exc)
    return filled


def town_facts(community) -> dict:
    """The compact version Jev gets with the readership: shares and counts only."""
    d = community.demographics or {}
    if not d.get("population"):
        return {}
    population, languages = d["population"], d.get("languages", {})
    facts = {
        "population": population.get("total"),
        "share_foreign_language_speakers_pct": population.get("foreign_language_pct"),
        "share_swedish_speakers_pct": population.get("swedish_pct"),
        "sami_speakers": population.get("sami_speakers"),
        "largest_foreign_languages": [lang["name"] for lang in languages.get("top_foreign", [])[:5]],
        "share_aged_65_or_over_pct": population.get("over_64_pct"),
    }
    if d.get("students", {}).get("pct") is not None:
        facts["share_students_pct"] = d["students"]["pct"]
    if d.get("tourism", {}).get("beds_per_1000_residents") is not None:
        facts["tourist_beds_per_1000_residents"] = d["tourism"]["beds_per_1000_residents"]
    facts["not_counted"] = "People without a municipality of residence, e.g. temporary protection and most seasonal workers"
    facts["source"] = f"{SOURCE}, {population.get('year')}"
    return facts
