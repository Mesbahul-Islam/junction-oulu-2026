"""The sports desk: a background agent that follows every player someone has in their team.

Each cycle (Celery beat, every 30 minutes):
  1. Kaleva's ice hockey and sports RSS feeds are fetched once (two requests), not once per player.
  2. Every followed player gets their own task (rate limited, see tasks.desk_player) that
     - reads the player's Liiga game log and writes a form note from his last games,
     - checks the Liiga profile for a suspension change,
     - stores Kaleva stories that mention him by name, with a link to the story.

Numbers come from Liiga; an AI model may reword the form note, and only keeps its version when it
adds no numbers (see analysis.reword).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone as dt_timezone
from email.utils import parsedate_to_datetime

from django.db.models import Count, F
from django.utils import timezone

from ..models import Fixture, Player, PlayerNote
from . import analysis
from .liiga import LiigaClient

logger = logging.getLogger(__name__)

SPORTS_FEEDS = [
    "https://www.kaleva.fi/feedit/rss/managed-listing/jaakiekko/",
    "https://www.kaleva.fi/feedit/rss/managed-listing/urheilu/",
]
USER_AGENT = "OuluNewsroomBot/1.0 (+hackathon prototype; sports desk)"
FORM_GAMES = 5
PLAYERS_PER_CYCLE = 60
LIIGA_MIN_INTERVAL = 1.5  # seconds between Liiga requests from one worker process

_last_liiga_call = 0.0


def _throttle() -> None:
    """Space out Liiga requests (the Celery task's rate_limit caps how many players run per minute)."""
    global _last_liiga_call
    wait = LIIGA_MIN_INTERVAL - (time.monotonic() - _last_liiga_call)
    if wait > 0:
        time.sleep(wait)
    _last_liiga_call = time.monotonic()


def fetch_sports_entries() -> list[dict]:
    """Recent Kaleva sports stories: [{url, title, summary, published}]."""
    import feedparser
    import httpx

    from apps.agents.graph.text import clean_html

    entries = []
    for url in SPORTS_FEEDS:
        try:
            resp = httpx.get(url, timeout=20, follow_redirects=True, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()
        except Exception as exc:
            logger.info("Sports feed %s unavailable: %s", url, exc)
            continue
        for e in feedparser.parse(resp.content).entries:
            link = (e.get("link") or "").split("?")[0].split("#")[0]  # same story, different tracking tags
            title = clean_html(e.get("title", ""))
            if not link or any(x["url"] == link or x["title"] == title for x in entries):
                continue
            published = None
            if e.get("published"):
                try:
                    published = parsedate_to_datetime(e["published"]).isoformat()
                except (TypeError, ValueError):
                    pass
            entries.append({"url": link, "title": title,
                            "summary": clean_html(e.get("summary", ""))[:600], "published": published})
    return entries


def mentions(entry: dict, player: Player) -> bool:
    text = f"{entry['title']} {entry['summary']}".casefold()
    return f"{player.first_name} {player.last_name}".casefold() in text


def followed_players(limit: int = PLAYERS_PER_CYCLE):
    """Players in at least one squad, least recently checked first."""
    return (Player.objects.filter(squad_picks__isnull=False, active=True).annotate(owners=Count("squad_picks"))
            .order_by(F("desk_checked_at").asc(nulls_first=True), "-owners")[:limit])


# --------------------------------------------------------------------------- one player


def _mmss(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


def form_text(f: dict, lang: str) -> tuple[str, list[str]]:
    """Title and sentences for a form note, in English or Finnish. The player's name is shown with it."""
    fi, n = lang == "fi", f["n"]
    goals, assists, ppp, pm, toi = f["goals"], f["assists"], f["ppp"], f["pm"], f["toi"]
    points = goals + assists
    if f.get("goalie"):
        return (f"{n} ottelua viime aikoina" if fi else f"{n} games played recently"), []
    if points == 0:
        title = f"Ei pisteitä viimeisessä {n} ottelussa" if fi else f"No points in his last {n} games"
        lines = [f"Peliaikaa {_mmss(toi)} ottelussa." if fi else f"He has played {_mmss(toi)} a game in that time."] if toi else []
        return title, lines
    if fi:
        title = f"{points} {'piste' if points == 1 else 'pistettä'} viimeisessä {n} ottelussa"
        lines = [f"{goals} {'maali' if goals == 1 else 'maalia'} ja {assists} {'syöttö' if assists == 1 else 'syöttöä'}"
                 + (f", joista {ppp} ylivoimalla." if ppp else ".")]
        if toi:
            lines.append(f"Peliaikaa {_mmss(toi)} ottelussa" + (f", plusmiinus {pm:+d}." if pm else "."))
    else:
        title = f"{points} point{'s' if points != 1 else ''} in his last {n} games"
        lines = [f"He has {goals} goal{'s' if goals != 1 else ''} and {assists} assist{'s' if assists != 1 else ''}"
                 + (f", {ppp} of the points on the power play." if ppp else ".")]
        if toi:
            lines.append(f"He plays {_mmss(toi)} a game" + (f" and is {pm:+d} over that stretch." if pm else "."))
    return title, lines


def form_note(player: Player, games: list[dict], ai: bool) -> PlayerNote | None:
    """Recent form from the player's Liiga game log (regular-season games only)."""
    regular = set(Fixture.objects.filter(season__is_current=True, serie="RUNKOSARJA").values_list("liiga_id", flat=True))
    played = [g for g in games if (g.get("game") or {}).get("fihaID") in regular and (g.get("game") or {}).get("finished")
              and not (g.get("gamePlayer") or {}).get("absent")]
    played.sort(key=lambda g: g["game"]["date"], reverse=True)
    last = played[:FORM_GAMES]
    if not last:
        return None
    n = len(last)
    facts = {
        "n": n, "goalie": player.position == "G",
        "goals": sum(g.get("goals") or 0 for g in last),
        "assists": sum(g.get("assists") or 0 for g in last),
        "ppp": sum(g.get("powerplayPoints") or 0 for g in last),
        "pm": sum(g.get("plusMinusDiff") or 0 for g in last),
        "toi": sum(g.get("timeOnIce") or 0 for g in last) / n,
    }
    title, lines = form_text(facts, "en")
    lines, wording = analysis.reword(lines, "a short form note about a hockey player", ai)
    published = datetime.fromisoformat(last[0]["game"]["date"]).replace(hour=21, tzinfo=dt_timezone.utc)
    note, _ = PlayerNote.objects.update_or_create(
        player=player, key="form",
        defaults={"kind": PlayerNote.Kind.FORM, "title": title, "body": " ".join(lines), "source": "liiga",
                  "url": "", "wording": wording, "published_at": published, "facts": facts},
    )
    return note


def run_player(player: Player, entries: list[dict], client: LiigaClient | None = None, ai: bool = True) -> dict:
    client = client or LiigaClient()
    season = player.team.home_fixtures.values_list("season__liiga_season", flat=True).first() if player.team else None
    done = {"form": False, "status": False, "news": 0}

    if season:
        try:
            _throttle()
            games = client.get(f"/players/web/info/{player.liiga_id}/games/{season}")
            done["form"] = form_note(player, games if isinstance(games, list) else [], ai) is not None
        except Exception as exc:
            logger.info("No game log for %s: %s", player, exc)
    try:
        _throttle()
        profile = client.get(f"/players/web/{player.liiga_id}")
        suspended = bool(profile.get("isSuspended"))
        if suspended != player.suspended:
            player.suspended = suspended
            player.save(update_fields=["suspended", "updated_at"])
            PlayerNote.objects.update_or_create(
                player=player, key=f"status:{timezone.localdate()}",
                defaults={"kind": PlayerNote.Kind.STATUS, "source": "liiga", "published_at": timezone.now(),
                          "facts": {"suspended": suspended},
                          "title": "Suspended" if suspended else "Available again"},
            )
            done["status"] = True
    except Exception as exc:
        logger.info("No Liiga profile for %s: %s", player, exc)

    for e in entries:
        _, new = PlayerNote.objects.get_or_create(
            player=player, key=e["url"][:300],
            defaults={"kind": PlayerNote.Kind.NEWS, "title": e["title"][:300], "body": e["summary"], "url": e["url"],
                      "source": "kaleva", "published_at": e["published"] or timezone.now()},
        )
        done["news"] += new
    player.desk_checked_at = timezone.now()
    player.save(update_fields=["desk_checked_at", "updated_at"])
    return done


def hand_to_newsroom(entries: list[dict]) -> int:
    """Give stories about followed players to the newsroom, which writes them up as stories in our
    app (summary, explainer, translations) for an editor to approve. Returns how many were new."""
    from apps.agents.newsroom.wire import store

    new = 0
    for e in entries:
        try:
            new += store({"url": e["url"], "title": e["title"], "body": e["summary"], "image_url": ""}) is not None
        except Exception as exc:
            logger.info("Newsroom hand-off failed for %s: %s", e["url"], exc)
    return new
