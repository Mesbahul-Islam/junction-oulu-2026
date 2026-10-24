"""Match analysis and coaching notes built from Liiga data.

Every sentence is assembled from computed facts (results, standings, form, head-to-head,
fantasy points), so nothing is invented. If an AI model is configured, it may reword the
notes, but a reworded note is only used when every number in it appears in the facts it was
given; otherwise the plain version is shown. Responses say which one the reader got.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Avg, Q, Sum

from .. import rules
from ..models import Fixture, Gameweek, GameweekScore, Player, PlayerGameStat, Squad, Team
from .squads import lineup_for, next_open_gameweek

logger = logging.getLogger(__name__)

REGULAR = "RUNKOSARJA"
OT_TYPES = {"ENDED_DURING_EXTENDED_GAME_TIME": "overtime", "ENDED_DURING_WINNING_SHOT_COMPETITION": "a shootout"}
FORM_GAMES = 3  # "form" = fantasy points per game over a player's last few games


def ordinal(n: int) -> str:
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _num(x, lang: str = "en") -> str:
    x = float(x)
    out = str(int(x)) if x == int(x) else f"{x:.1f}"
    return out.replace(".", ",") if lang == "fi" else out  # Finnish uses a decimal comma


def p_fi(x) -> str:
    """Finnish points with the right number: "1 piste", "2,5 pistettä"."""
    return f"{_num(x, 'fi')} {'piste' if float(x) == 1 else 'pistettä'}"


def place(n: int, lang: str = "en") -> str:
    """1st / 1."""
    return f"{n}." if lang == "fi" else ordinal(n)


def lang_of(user) -> str:
    """Lämäri is written in Finnish for Finnish readers and in English for everyone else."""
    return "fi" if getattr(user, "preferred_language", "") == "fi" else "en"


# --------------------------------------------------------------------------- league table, form, head-to-head


def standings(season, before=None) -> list[dict]:
    """Regular-season table: 3 points for a regulation win, 2 for an OT/shootout win, 1 for an OT/shootout loss."""
    qs = season.fixtures.filter(serie=REGULAR, status=Fixture.Status.FINISHED)
    if before is not None:
        qs = qs.filter(starts_at__lt=before)
    table: dict[int, dict] = defaultdict(lambda: {"gp": 0, "pts": 0, "gf": 0, "ga": 0, "w": 0})
    for f in qs:
        extra = f.finished_type in OT_TYPES
        for team, gf, ga in ((f.home_id, f.home_goals or 0, f.away_goals or 0), (f.away_id, f.away_goals or 0, f.home_goals or 0)):
            row = table[team]
            row["gp"] += 1
            row["gf"] += gf
            row["ga"] += ga
            if gf > ga:
                row["pts"] += 2 if extra else 3
                row["w"] += 1
            elif extra:
                row["pts"] += 1
    names = dict(Team.objects.filter(pk__in=table).values_list("pk", "name"))
    rows = sorted(({"team_id": t, "team": names.get(t, ""), **r} for t, r in table.items()),
                  key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"]))
    for i, r in enumerate(rows, start=1):
        r["rank"] = i
    return rows


def _rank_of(table, team_id) -> dict | None:
    return next((r for r in table if r["team_id"] == team_id), None)


def form(season, team_id, before=None, games=5) -> list[str]:
    """Last results, newest first: W, L, OTW (won in OT/shootout), OTL."""
    qs = season.fixtures.filter(Q(home_id=team_id) | Q(away_id=team_id), status=Fixture.Status.FINISHED, serie=REGULAR)
    if before is not None:
        qs = qs.filter(starts_at__lt=before)
    out = []
    for f in qs.order_by("-starts_at")[:games]:
        gf, ga = (f.home_goals, f.away_goals) if f.home_id == team_id else (f.away_goals, f.home_goals)
        extra = f.finished_type in OT_TYPES
        out.append(("OTW" if extra else "W") if gf > ga else ("OTL" if extra else "L"))
    return out


def head_to_head(fixture) -> list[Fixture]:
    return list(fixture.season.fixtures.filter(
        Q(home=fixture.home, away=fixture.away) | Q(home=fixture.away, away=fixture.home),
        status=Fixture.Status.FINISHED, starts_at__lt=fixture.starts_at,
    ).select_related("home", "away").order_by("starts_at"))


def _wins(results) -> int:
    return sum(1 for r in results if r in ("W", "OTW"))


def player_form(player_ids, games=FORM_GAMES) -> dict[int, dict]:
    """{player: {"avg": points per game over the last `games` played, "games": n}}."""
    out = {}
    stats = PlayerGameStat.objects.filter(player_id__in=player_ids, stats__played=True).order_by("player_id", "-fixture__starts_at")
    for pid, pts in stats.values_list("player_id", "points"):
        row = out.setdefault(pid, {"pts": [], "avg": 0.0, "games": 0})
        if len(row["pts"]) < games:
            row["pts"].append(float(pts))
    for row in out.values():
        row["games"] = len(row["pts"])
        row["avg"] = round(sum(row["pts"]) / row["games"], 1) if row["games"] else 0.0
    return out


def games_in(gameweek: Gameweek) -> dict[int, int]:
    """How many games each team plays in a gameweek."""
    counts: dict[int, int] = defaultdict(int)
    for home, away in gameweek.fixtures.values_list("home_id", "away_id"):
        counts[home] += 1
        counts[away] += 1
    return counts


# --------------------------------------------------------------------------- optional AI wording, number-checked


def _numbers(text: str) -> set[str]:
    return {n.rstrip(".").replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", text)}


def model_ready() -> bool:
    """Is the configured model usable right now? Checked with a 2 s timeout, remembered for 5 minutes,
    so background jobs skip AI wording at once when the model server is down."""
    hit = cache.get("fx-model-ready")
    if hit is not None:
        return hit
    from apps.agents.graph.llm import ollama_model_problem, resolve

    info = resolve("sports")
    ready = not info["stub_reason"] and not ollama_model_problem(info)
    cache.set("fx-model-ready", ready, 300)
    return ready


def ai_budget() -> bool:
    """Take one model call from the per-minute budget shared by all workers (Redis). False when spent."""
    import time

    from django.conf import settings

    try:
        import redis

        r = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        key = f"fx-ai-budget:{int(time.time() // 60)}"
        used = r.incr(key)
        r.expire(key, 90)
        return used <= settings.SPORTS_AI_PER_MINUTE
    except Exception:  # no Redis (local dev): fall back to this process only
        key = f"fx-ai-budget:{int(time.time() // 60)}"
        cache.add(key, 0, 90)
        return cache.incr(key) <= settings.SPORTS_AI_PER_MINUTE


def reword(notes: list[str], purpose: str, ai: bool = True, lang: str = "en") -> tuple[list[str], str]:
    """Let the configured model reword `notes`; keep its version only if it adds no new numbers.

    Only background jobs pass ai=True: readers never wait on a model. Returns (notes, source)
    where source is "ai" only when the model's own wording is used.
    """
    from django.conf import settings

    if not ai or not notes or not getattr(settings, "LLM_MODEL", "") or settings.LLM_MODEL == "stub" or not model_ready():
        return notes, "data"
    key = "fx-reword:" + str(abs(hash((purpose, lang, tuple(notes)))))
    if (hit := cache.get(key)) is not None:
        return hit
    if not ai_budget():
        return notes, "data"  # over this minute's model budget: plain notes now, AI wording on a later run
    try:
        from pydantic import BaseModel

        from apps.agents.graph.llm import structured_call

        class Notes(BaseModel):
            notes: list[str]

        prompt = (
            f"You write {purpose} for an ice hockey fantasy app. Rewrite each note below as one short, plain "
            f"sentence a fan would say, in {'Finnish' if lang == 'fi' else 'English'}. Keep every name and number "
            "exactly. Do not add facts, numbers, hype words, dashes or emojis. Return the same number of notes in "
            "the same order.\n\n"
            + "\n".join(f"- {n}" for n in notes)
        )
        result = structured_call(prompt, Notes, fallback=lambda: {"notes": notes}, agent="sports").notes
        allowed = set().union(*(_numbers(n) for n in notes))
        if len(result) == len(notes) and all(_numbers(r) <= allowed and r.strip() for r in result):
            out = ([r.strip().replace("—", ",").replace("–", "-") for r in result], "ai")
        else:
            out = (notes, "data")
    except Exception as exc:  # model down or slow: plain notes are always fine
        logger.info("Reword skipped: %s", exc)
        out = (notes, "data")
    cache.set(key, out, 3600)
    return out


# --------------------------------------------------------------------------- match analysis


def _player_line(stat, lang: str) -> str:
    s, name = stat.stats, stat.player.name
    fi = lang == "fi"
    bits = []
    if s.get("goals"):
        g = s["goals"]
        bits.append(f"{g} {'maali' if g == 1 else 'maalia'}" if fi else f"{g} goal{'s' if g > 1 else ''}")
    if s.get("assists"):
        a = s["assists"]
        bits.append(f"{a} {'syöttö' if a == 1 else 'syöttöä'}" if fi else f"{a} assist{'s' if a > 1 else ''}")
    if s.get("goalie") and s.get("saves"):
        bits.append(f"{s['saves']} {'torjuntaa' if fi else 'saves'}")
    return f"{name} ({', '.join(bits)})" if bits else name


def match_analysis(fixture: Fixture, squad: Squad | None = None, detail: str = "short", ai: bool = False,
                   reader: str = "fan", lang: str = "en") -> dict:
    """Context beyond the score for a finished game, or a preview for an upcoming one.

    detail: "short" (three lines) or "full". reader: "fan" (numbers first) or "new" (explains the
    rules the result depends on, for people new to Finnish hockey). lang: "en" or "fi"."""
    fi = lang == "fi"
    n = lambda x: _num(x, lang)
    season = fixture.season
    home, away = fixture.home, fixture.away
    before = standings(season, before=fixture.starts_at)
    hb, ab = _rank_of(before, home.pk), _rank_of(before, away.pk)
    h2h = head_to_head(fixture)
    mine = set(squad.picks.values_list("player_id", flat=True)) if squad else set()
    notes, sections = [], []

    if fixture.status == Fixture.Status.FINISHED:
        hg, ag = fixture.home_goals or 0, fixture.away_goals or 0
        winner, loser, wg, lg = (home, away, hg, ag) if hg > ag else (away, home, ag, hg)
        ot = fixture.finished_type in OT_TYPES
        if fi:
            how = {"ENDED_DURING_EXTENDED_GAME_TIME": " jatkoajalla", "ENDED_DURING_WINNING_SHOT_COMPETITION": " voittolaukauskilpailussa"}.get(fixture.finished_type, "")
            notes.append(f"{winner.name} voitti{how} {wg}-{lg}. Vastassa oli {loser.name}.")
        else:
            how = f" in {OT_TYPES[fixture.finished_type]}" if ot else ""
            notes.append(f"{winner.name} beat {loser.name} {wg}-{lg}{how}.")
        after = standings(season, before=fixture.starts_at + timedelta(hours=4))  # table including this game
        wa, wb = _rank_of(after, winner.pk), _rank_of(before, winner.pk)
        if wa and wb and wa["rank"] != wb["rank"]:
            up = wa["rank"] < wb["rank"]
            notes.append(f"{winner.name} {'nousi' if up else 'putosi'} sijalle {wa['rank']}, {p_fi(wa['pts'])}." if fi
                         else f"{winner.name} move {'up' if up else 'down'} to {ordinal(wa['rank'])} with {wa['pts']} points.")
        elif wa:
            notes.append(f"{winner.name} pysyi sijalla {wa['rank']}, {p_fi(wa['pts'])}." if fi
                         else f"{winner.name} stay {ordinal(wa['rank'])} with {wa['pts']} points.")
        la = _rank_of(after, loser.pk)
        if la:
            notes.append(f"{loser.name} on sijalla {la['rank']}, {p_fi(la['pts'])}." if fi
                         else f"{loser.name} are {ordinal(la['rank'])} on {la['pts']} points.")
        stats = list(fixture.player_stats.filter(stats__played=True).select_related("player").order_by("-points"))
        scorers = [s for s in stats if s.stats.get("goals")]
        if scorers:
            notes.append(("Maalit: " if fi else "Goals: ") + ", ".join(_player_line(s, lang) for s in scorers[:4]) + ".")
        if stats:
            top = stats[0]
            notes.append(f"Ottelun eniten Lämäri-pisteitä: {top.player.name}, {p_fi(top.points)}." if fi
                         else f"Top fantasy score: {top.player.name} with {n(top.points)} points.")
        lf = form(season, loser.pk, before=fixture.starts_at)
        if len(lf) >= 3 and _wins(lf) == 0:
            notes.append(f"{loser.name} on hävinnyt nyt {len(lf) + 1} ottelua peräkkäin." if fi
                         else f"{loser.name} have now lost {len(lf) + 1} in a row.")
        yours = [s for s in stats if s.player_id in mine]
        if yours:
            sections.append({"title": "Sinun pelaajasi" if fi else "Your players",
                             "lines": [f"{s.player.name}: {n(s.points)} {'pistettä' if fi else 'points'}" for s in yours]})
        if detail == "full" and stats:
            sections.append({"title": "Lämäri-pisteet" if fi else "Fantasy points",
                             "lines": [f"{s.player.name}: {n(s.points)}" for s in stats[:8]]})
    else:
        if hb and ab:
            notes.append(f"Kotona {home.name} (sija {hb['rank']}, {p_fi(hb['pts'])}), vieraana {away.name} (sija {ab['rank']}, {p_fi(ab['pts'])})." if fi
                         else f"{home.name} ({ordinal(hb['rank'])}, {hb['pts']} points) host {away.name} ({ordinal(ab['rank'])}, {ab['pts']} points).")
        hf, af = form(season, home.pk, fixture.starts_at), form(season, away.pk, fixture.starts_at)
        if hf and af:
            notes.append(f"Viime otteluista {home.name} on voittanut {_wins(hf)}/{len(hf)} ja {away.name} {_wins(af)}/{len(af)}." if fi
                         else f"{home.name} have won {_wins(hf)} of their last {len(hf)}, {away.name} {_wins(af)} of {len(af)}.")
        if h2h:
            last = h2h[-1]
            notes.append(f"Edellinen kohtaaminen {last.starts_at:%d.%m.}: {last.home.name} {last.home_goals}-{last.away_goals} {last.away.name}." if fi
                         else f"They met on {last.starts_at:%d.%m.}: {last.home.name} {last.home_goals}-{last.away_goals} {last.away.name}.")
        players = list(Player.objects.filter(team__in=[home, away], active=True))
        pf = player_form([p.pk for p in players])
        watch = sorted((p for p in players if pf.get(p.pk, {}).get("games", 0) >= 2), key=lambda p: -pf[p.pk]["avg"])[:3]
        if watch:
            per = "pistettä/ottelu" if fi else "per game"
            notes.append(("Kovassa vireessä: " if fi else "In form: ") + ", ".join(f"{p.name} ({n(pf[p.pk]['avg'])} {per})" for p in watch) + ".")
        yours = [p for p in players if p.pk in mine]
        if yours:
            sections.append({"title": "Sinun pelaajasi tässä ottelussa" if fi else "Your players in this game", "lines": [
                f"{p.name}: {n(pf.get(p.pk, {}).get('avg', 0))} {'pistettä/ottelu viime aikoina' if fi else 'points per game lately'}" for p in yours]})

    if detail == "short":
        notes = notes[:3]
    if reader == "new":
        notes += explainers(fixture, lang)
    notes, source = reword(notes, "match summaries", ai, lang)
    return {
        "fixture": fixture.pk, "status": fixture.status, "detail": detail, "reader": reader, "lang": lang, "notes": notes,
        "sections": sections, "source": source,
        "table": [{k: r[k] for k in ("rank", "team", "pts", "gp")} for r in (hb, ab) if r],
    }


def explainers(fixture: Fixture, lang: str = "en") -> list[str]:
    """The rules a newcomer needs to read this game, only the ones that apply to it."""
    fi = lang == "fi"
    if fixture.finished_type == "ENDED_DURING_EXTENDED_GAME_TIME":
        first = ("Peli oli tasan 60 minuutin jälkeen, joten pelattiin jatkoaika. Jatkoaikavoitosta saa 2 pistettä ja häviäjäkin 1." if fi
                 else "It was tied after 60 minutes, so they played overtime. A win in overtime is worth 2 points and the losing team still gets 1.")
    elif fixture.finished_type == "ENDED_DURING_WINNING_SHOT_COMPETITION":
        first = ("Jatkoajalla ei syntynyt maalia, joten voittolaukauskilpailu ratkaisi. Voittaja saa 2 pistettä ja häviäjä 1." if fi
                 else "Overtime ended without a goal, so a shootout decided it. The winner gets 2 points and the loser 1.")
    elif fixture.status == Fixture.Status.FINISHED:
        first = "Varsinaisella peliajalla voitosta saa Liigassa 3 pistettä." if fi else "A win in regular time is worth 3 points in the Liiga table."
    else:
        first = ("Liigassa voitosta saa 3 pistettä, jatkoaika- tai voittolaukausvoitosta 2." if fi
                 else "Liiga teams get 3 points for a win in regular time, and 2 for a win in overtime or a shootout.")
    second = ("Lämärissä pelaajat tuovat pisteitä maaleista, syötöistä ja torjunnoista sille, jonka joukkueessa he ovat." if fi
              else "In Lämäri, players earn points for goals, assists and saves for whoever has them in their team.")
    return [first, second]


# --------------------------------------------------------------------------- coach notes for one squad


def coach(squad: Squad, ai: bool = False, lang: str = "en") -> dict:
    """Review of your last gameweek and concrete suggestions for the next one."""
    fi = lang == "fi"
    n = lambda x: _num(x, lang)
    per = "pistettä/ottelu" if fi else "points per game"
    season = squad.season
    picks = {p.player_id: p for p in squad.picks.select_related("player__team")}
    owned = {pid: pick.player for pid, pick in picks.items()}
    review, tips = [], []

    last = GameweekScore.objects.filter(squad=squad, final=True).select_related("gameweek").order_by("-gameweek__number").first()
    if last:
        gw = last.gameweek
        avg = GameweekScore.objects.filter(gameweek=gw).aggregate(a=Avg("total"))["a"] or 0
        better = GameweekScore.objects.filter(gameweek=gw, total__gt=last.total).count()
        managers = GameweekScore.objects.filter(gameweek=gw).count()
        review.append(f"{p_fi(last.total)}, keskiarvo oli {round(avg)}. Sijoituit {better + 1}./{managers}." if fi
                      else f"{n(last.total)} points, {'above' if last.total >= avg else 'below'} the average of {round(avg)}. You finished {ordinal(better + 1)} of {managers}.")
        detail = {d["player"]: d for d in last.detail}
        counted = last.detail
        if counted:
            best = max(counted, key=lambda d: d["points"])
            if best["player"] in owned:
                review.append(f"Paras pelaajasi: {owned[best['player']].name}, {p_fi(best['points'])}." if fi
                              else f"Best performer: {owned[best['player']].name} with {n(best['points'])} points.")
            cap = next((d for d in counted if d["multiplier"] > 1), None)
            if cap and best["player"] != cap["player"] and best["points"] > cap["points"] and cap["player"] in owned and best["player"] in owned:
                gain = best["points"] - cap["points"]
                c, b = owned[cap["player"]].last_name, owned[best["player"]].last_name
                review.append(f"Kapteeni {c} teki {p_fi(cap['points'])}. {b} kapteenina olisi tuonut {p_fi(gain)} lisää." if fi
                              else f"Captain {c} scored {n(cap['points'])}. Captaining {b} would have added {n(gain)} points.")
        lineup = lineup_for(squad, gw)
        if lineup:
            bench = [s.player_id for s in lineup.slots.all() if not s.is_starter and s.player_id not in detail]
            bench_pts = dict(PlayerGameStat.objects.filter(player_id__in=bench, fixture__gameweek=gw).values_list("player").annotate(s=Sum("points")))
            lost = {pid: pts for pid, pts in bench_pts.items() if pts and pts > 0}
            if lost:
                pid = max(lost, key=lost.get)
                review.append(f"{owned[pid].name} teki penkillä {p_fi(lost[pid])}." if fi
                              else f"{owned[pid].name} scored {n(lost[pid])} on your bench.")

    try:
        nxt = next_open_gameweek(season)
    except Exception:
        nxt = None
    if nxt:
        gwl = f"kierroksella {nxt.number}" if fi else f"GW{nxt.number}"
        lineup = lineup_for(squad, nxt)
        counts = games_in(nxt)
        pf = player_form(list(owned))
        starters = [s.player for s in lineup.slots.all() if s.is_starter] if lineup else []
        bench = [s.player for s in lineup.slots.all() if not s.is_starter] if lineup else []
        value = lambda p: pf.get(p.pk, {}).get("avg", 0) * counts.get(p.team_id, 0)
        avg_of = lambda p, f=pf: n(f.get(p.pk, {}).get("avg", 0))

        for p in starters:
            if p.injured or p.suspended:
                state = ("loukkaantunut" if p.injured else "pelikiellossa") if fi else ("injured" if p.injured else "suspended")
                tips.append({"kind": "lineup", "text": f"{p.name} on {state}. Siirrä hänet penkille ennen kierroksen {nxt.number} takarajaa." if fi
                             else f"{p.name} is {state}. Move him to the bench before the GW{nxt.number} deadline."})
        for p in starters:
            if counts.get(p.team_id, 0) == 0:
                tips.append({"kind": "lineup", "text": f"Joukkueella {p.team.name} ei ole otteluita {gwl}, joten {p.name} ei voi tehdä pisteitä. Siirrä hänet penkille." if fi
                             else f"{p.team.name} have no games in GW{nxt.number}, so {p.name} can't score. Bench him."})

        if starters:
            best = max(starters, key=value)
            if lineup and best.pk != lineup.captain_id and value(best) > 0:
                cur = owned.get(lineup.captain_id)
                if fi:
                    text = (f"Valitse kapteeniksi {best.name}: viime aikoina {avg_of(best)} {per} ja {counts.get(best.team_id, 0)} ottelua {gwl}."
                            + (f" Nykyinen kapteeni {cur.last_name}: {avg_of(cur)} {per} ja {counts.get(cur.team_id, 0)} ottelua." if cur else ""))
                else:
                    text = (f"Captain {best.name}: {avg_of(best)} points per game lately and {counts.get(best.team_id, 0)} games in GW{nxt.number}"
                            + (f", against {avg_of(cur)} per game and {counts.get(cur.team_id, 0)} games for {cur.last_name}." if cur else "."))
                tips.append({"kind": "captain", "player": best.pk, "text": text})

        for b in bench:
            weaker = [s for s in starters if s.position == b.position and value(b) > value(s) + 2]
            if weaker:
                s = min(weaker, key=value)
                tips.append({"kind": "lineup", "text":
                    f"Aloittajaksi {b.name}, penkille {s.name}: {avg_of(b)} vs {avg_of(s)} {per}, {counts.get(b.team_id, 0)} vs {counts.get(s.team_id, 0)} ottelua." if fi
                    else f"Start {b.name} instead of {s.name}: {avg_of(b)} vs {avg_of(s)} points per game, "
                         f"{counts.get(b.team_id, 0)} vs {counts.get(s.team_id, 0)} games."})
                break

        # One transfer idea: your weakest starter for the best affordable player in the same position.
        if starters:
            weakest = min(starters, key=value)
            per_team = defaultdict(int)
            for p in owned.values():
                per_team[p.team_id] += 1
            budget = picks[weakest.pk].purchase_price + squad.bank
            pool = Player.objects.filter(position=weakest.position, active=True, injured=False, suspended=False, price__lte=budget,
                                         team__isnull=False).exclude(pk__in=owned)
            cands = [p for p in pool if per_team[p.team_id] - (1 if p.team_id == weakest.team_id else 0) < rules.MAX_PER_TEAM]
            cf = player_form([p.pk for p in cands])
            score = lambda p: cf.get(p.pk, {}).get("avg", 0) * counts.get(p.team_id, 0)
            cands = [p for p in cands if cf.get(p.pk, {}).get("games", 0) >= 2]
            if cands:
                pick = max(cands, key=score)
                if score(pick) > value(weakest) + 3:
                    diff = picks[weakest.pk].purchase_price - pick.price
                    if fi:
                        money = f"säästät {n(diff)}" if diff > 0 else (f"maksaa {n(-diff)} enemmän" if diff < 0 else "sama hinta")
                        text = (f"Harkitse vaihtoa: ulos {weakest.name}, sisään {pick.name} ({pick.team.name}). "
                                f"{avg_of(pick, cf)} vs {avg_of(weakest)} {per}, {counts.get(pick.team_id, 0)} vs {counts.get(weakest.team_id, 0)} ottelua {gwl}, {money}.")
                    else:
                        money = f"saves {n(diff)}" if diff > 0 else (f"costs {n(-diff)} more" if diff < 0 else "same price")
                        text = (f"Consider {pick.name} ({pick.team.name}) for {weakest.name}: {avg_of(pick, cf)} vs {avg_of(weakest)} "
                                f"points per game, {counts.get(pick.team_id, 0)} vs {counts.get(weakest.team_id, 0)} games in GW{nxt.number}, {money}.")
                    tips.append({"kind": "transfer", "out": weakest.pk, "in": pick.pk, "text": text})

    review_text, review_source = reword(review, "a short review of a fantasy manager's week", ai, lang)
    tip_texts, tip_source = reword([t["text"] for t in tips], "fantasy team suggestions", ai, lang)
    for t, text in zip(tips, tip_texts):
        t["text"] = text
    return {
        "gameweek": last.gameweek.number if last else None,
        "next_gameweek": nxt.number if nxt else None,
        "lang": lang,
        "review": review_text,
        "tips": tips,
        "source": "ai" if "ai" in (review_source, tip_source) else "data",
    }
