"""Which municipality a point is in, and which newsroom community serves it.

The borders are Statistics Finland's municipality map (1:1 000 000, CC BY 4.0), saved in
data/municipality_borders.json so a lookup needs no outside service. Refresh it once a year
with ``manage.py fetch_demographics --borders`` and commit the file.

Privacy: the reader app sends coordinates once, to ``POST /api/accounts/locate/``. They are
only used for this lookup and are never stored or logged; the profile keeps the municipality.
"""

from __future__ import annotations

import functools
import json
import math
from pathlib import Path

import httpx

BORDERS = Path(__file__).parent / "data" / "municipality_borders.json"
WFS = "https://geo.stat.fi/geoserver/tilastointialueet/wfs"
LAYER = "tilastointialueet:kunta1000k_{year}"
PRECISION = 4  # decimal places, about 10 m: plenty for a municipality border


def write_borders(year: int) -> int:
    """Download the municipality map for ``year`` and write the compact file. Returns how many."""
    resp = httpx.get(WFS, timeout=120, params={
        "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeName": LAYER.format(year=year),
        "outputFormat": "application/json", "srsName": "EPSG:4326"})
    resp.raise_for_status()
    towns = {}
    for feature in resp.json()["features"]:
        geometry = feature["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        polygons = [[_ring(ring) for ring in polygon] for polygon in polygons]
        xs = [x for polygon in polygons for x, _ in polygon[0]]
        ys = [y for polygon in polygons for _, y in polygon[0]]
        towns[feature["properties"]["kunta"]] = {
            "name": feature["properties"]["nimi"],
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
            "polygons": polygons,
        }
    if not towns:
        raise ValueError("The map service returned no municipalities")
    BORDERS.parent.mkdir(exist_ok=True)
    payload = {"source": "Statistics Finland, municipality map 1:1 000 000", "licence": "CC BY 4.0",
               "layer": LAYER.format(year=year), "municipalities": dict(sorted(towns.items()))}
    BORDERS.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    load_borders.cache_clear()
    return len(towns)


def _ring(ring):
    out = []
    for x, y in ring:
        point = [round(x, PRECISION), round(y, PRECISION)]
        if not out or point != out[-1]:
            out.append(point)
    return out


@functools.lru_cache(maxsize=1)
def load_borders() -> dict[str, dict]:
    try:
        return json.loads(BORDERS.read_text(encoding="utf-8"))["municipalities"]
    except FileNotFoundError:
        return {}


def _inside(lng: float, lat: float, polygon) -> bool:
    """Even-odd ray casting over the outer ring and any holes."""
    inside = False
    for ring in polygon:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                inside = not inside
            j = i
    return inside


def locate(lat: float, lng: float) -> str | None:
    """The three-digit code of the municipality the point is in, or None (sea, abroad)."""
    for code, town in load_borders().items():
        min_x, min_y, max_x, max_y = town["bbox"]
        if min_x <= lng <= max_x and min_y <= lat <= max_y and any(_inside(lng, lat, p) for p in town["polygons"]):
            return code
    return None


def _center(code: str):
    town = load_borders().get(code)
    if not town:
        return None
    min_x, min_y, max_x, max_y = town["bbox"]
    return (min_x + max_x) / 2, (min_y + max_y) / 2


def _km(a, b) -> float:
    (lng1, lat1), (lng2, lat2) = a, b
    dlat, dlng = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    h = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def municipality_name(code: str) -> str:
    town = load_borders().get(code)
    if town:
        return town["name"]
    from .demographics import load_snapshot

    return load_snapshot().get(code, {}).get("municipality", "")


def newsrooms() -> dict[str, "CommunityGroup"]:  # noqa: F821
    """{municipality code: active geographic community} for the towns the newsroom covers."""
    from .demographics import DemographicsError, municipality_code
    from .models import CommunityGroup

    out = {}
    for group in CommunityGroup.objects.filter(kind=CommunityGroup.Kind.GEO, is_active=True).exclude(municipality=""):
        code = group.municipality_code
        if not code:
            try:
                code = municipality_code(group.municipality)
            except DemographicsError:
                continue
        out.setdefault(code, group)
    return out


def town(code: str) -> dict:
    """What the reader app shows for a municipality: whether we cover it, and if not, the
    nearest town we do."""
    covered = newsrooms()
    community = covered.get(code)
    nearest = None
    if community is None and covered:
        here = _center(code)
        if here:
            distances = [(_km(here, _center(c)), c) for c in covered if _center(c)]
            if distances:
                km, nearest_code = min(distances)
                nearest = {**_community(covered[nearest_code]), "km": round(km)}
    return {"code": code, "name": municipality_name(code), "covered": community is not None,
            "community": _community(community) if community else None, "nearest": nearest}


def _community(group) -> dict:
    return {"slug": group.slug, "name": group.name, "municipality": group.municipality}


def municipalities() -> list[dict]:
    """Every municipality, for the town picker, with the ones we cover marked."""
    covered = newsrooms()
    names = {code: town["name"] for code, town in load_borders().items()}
    if not names:
        from .demographics import load_snapshot

        names = {code: rec["municipality"] for code, rec in load_snapshot().items()}
    return sorted(({"code": code, "name": name, "covered": code in covered} for code, name in names.items()),
                  key=lambda m: m["name"])
