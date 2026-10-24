from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.communities.models import CommunityGroup, Membership
from apps.fantasy import rules
from apps.fantasy.models import (
    DailyScore,
    Fixture,
    Gameweek,
    GameweekScore,
    Player,
    PlayerGameStat,
    Position,
    Season,
    Squad,
    Team,
)
from apps.fantasy.services import leaderboards, liiga
from apps.fantasy.services.scoring import score_gameweek
from apps.fantasy.services.squads import FantasyError, create_squad, make_transfers, set_lineup

D = Decimal
G, DEF, F = Position.GOALIE, Position.DEFENCE, Position.FORWARD


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def world(db):
    """A season with 6 teams x 6 players (1 G, 2 D, 3 F), one past and one upcoming gameweek."""
    now = timezone.now()
    season = Season.objects.create(liiga_season=2027, name="2026-27", is_current=True)
    gw1 = Gameweek.objects.create(season=season, number=1, deadline=now - timedelta(days=3), status=Gameweek.Status.LIVE)
    gw2 = Gameweek.objects.create(season=season, number=2, deadline=now + timedelta(days=2))
    teams = [Team.objects.create(liiga_id=f"{i}:t{i}", name=f"Team {i}") for i in range(6)]
    n = 0
    for team in teams:
        for pos in (G, DEF, DEF, F, F, F):
            n += 1
            Player.objects.create(liiga_id=n, first_name="P", last_name=str(n), team=team, position=pos, price=D("6.0"))
    return {"season": season, "gw1": gw1, "gw2": gw2, "teams": teams}


def pick_squad(exclude=()):
    """15 valid player ids: 2 G, 5 D, 8 F, max 3 per team."""
    need = dict(rules.SQUAD_COMPOSITION)
    per_team, ids = {}, []
    for p in Player.objects.exclude(pk__in=exclude).order_by("pk"):
        if need[p.position] and per_team.get(p.team_id, 0) < rules.MAX_PER_TEAM:
            ids.append(p.pk)
            need[p.position] -= 1
            per_team[p.team_id] = per_team.get(p.team_id, 0) + 1
    assert len(ids) == rules.SQUAD_SIZE
    return ids


def spare(squad, position, n):
    """n unowned players of `position` that keep the squad within MAX_PER_TEAM."""
    owned = list(Player.objects.filter(squad_picks__squad=squad))
    per_team = {}
    for p in owned:
        per_team[p.team_id] = per_team.get(p.team_id, 0) + 1
    out = []
    for p in Player.objects.filter(position=position).exclude(pk__in=[o.pk for o in owned]).order_by("pk"):
        if per_team.get(p.team_id, 0) < rules.MAX_PER_TEAM:
            out.append(p.pk)
            per_team[p.team_id] = per_team.get(p.team_id, 0) + 1
        if len(out) == n:
            return out
    raise AssertionError("not enough spare players")


def make_user(django_user_model, n):
    return django_user_model.objects.create_user(email=f"u{n}@example.com", password="x-pass-123")


def make_squad_in_gw1(user, world, name="Team"):
    """Create a squad whose first gameweek is gw1 (as if built before its deadline)."""
    gw1 = world["gw1"]
    deadline = gw1.deadline
    gw1.deadline = timezone.now() + timedelta(hours=1)
    gw1.save()
    squad = create_squad(user, name, pick_squad())
    gw1.deadline = deadline
    gw1.save()
    return squad


# --------------------------------------------------------------------------- points


def test_forward_hat_trick_points():
    pts, b = rules.game_points(F, {"played": True, "toi": 1200, "goals": 3, "assists": 1, "plusminus": 2,
                                   "shots": 7, "winning_goal": 1, "penalty_minutes": 2})
    assert b == {"appearance": 1, "goals": 12, "assists": 3, "winning_goal": 1, "penalties": -1,
                 "full_shift": 1, "plus_minus": 2, "shots": 2}
    assert pts == 21


def test_defence_and_goalie_shutouts():
    d_pts, d = rules.game_points(DEF, {"played": True, "toi": 600, "goals": 1, "team_goals_against": 0})
    assert d == {"appearance": 1, "goals": 6, "shutout": 3} and d_pts == 10
    g_pts, g = rules.game_points(G, {"played": True, "saves": 31, "goals_allowed": 0, "periods_played": 3,
                                     "goalie_win": True})
    assert g == {"appearance": 1, "saves": 6, "win": 3, "shutout": 5} and g_pts == 15


def test_did_not_play_scores_zero():
    assert rules.game_points(F, {"played": False, "goals": 0}) == (0, {})


def test_price_curve():
    assert rules.price_for_percentile(0) == D("4.0")
    assert rules.price_for_percentile(1) == D("13.0")
    assert D("6.0") <= rules.price_for_percentile(0.5) <= D("6.5")


# --------------------------------------------------------------------------- squads


def test_create_squad_rules(world, django_user_model):
    user = make_user(django_user_model, 1)
    ids = pick_squad()
    with pytest.raises(FantasyError, match="exactly 15"):
        create_squad(user, "x", ids[:-1])
    too_many_from_team = list(Player.objects.filter(team=world["teams"][0]).values_list("pk", flat=True)[:4])
    with pytest.raises(FantasyError):
        create_squad(user, "x", too_many_from_team + ids[4:])
    Player.objects.filter(pk=ids[0]).update(price=D("20.0"))
    with pytest.raises(FantasyError, match="over the"):
        create_squad(user, "x", ids)
    Player.objects.filter(pk=ids[0]).update(price=D("6.0"))

    squad = create_squad(user, "Pörssi Kings", ids)
    assert squad.bank == D("100.0") - 15 * D("6.0")
    assert squad.first_gameweek == world["gw2"]  # gw1's deadline has passed
    lineup = squad.lineups.get()
    assert [s.player.position for s in lineup.slots.all()].count(G) == 2
    assert sum(1 for s in lineup.slots.all() if s.is_starter) == 11
    with pytest.raises(FantasyError, match="already have"):
        create_squad(user, "again", ids)


def test_transfers_free_then_cost_points(world, django_user_model):
    user = make_user(django_user_model, 1)
    squad = make_squad_in_gw1(user, world)
    owned = list(squad.picks.values_list("player_id", flat=True))
    out_fwds = list(Player.objects.filter(pk__in=owned, position=F).values_list("pk", flat=True))
    # Swapping out first means the incoming players' teams have room.
    spare_fwds = spare(squad, F, 2)

    # gw2 is not the first gameweek: 1 free transfer, then 4 points each.
    t = make_transfers(squad, out_fwds[:2], spare_fwds[:2])
    assert [x.point_cost for x in t] == [0, rules.TRANSFER_POINT_COST]
    squad.refresh_from_db()
    assert squad.free_transfers == 0
    lineup = squad.lineups.get(gameweek=world["gw2"])
    assert set(spare_fwds[:2]) <= set(lineup.slots.values_list("player_id", flat=True))

    with pytest.raises(FantasyError, match="same position"):
        make_transfers(squad, [out_fwds[2]], list(Player.objects.filter(position=G).exclude(
            pk__in=squad.picks.values_list("player_id", flat=True)).values_list("pk", flat=True)[:1]))
    pricey = spare(squad, F, 1)[0]
    Player.objects.filter(pk=pricey).update(price=D("50.0"))
    with pytest.raises(FantasyError, match="Not enough money"):
        make_transfers(squad, [out_fwds[2]], [pricey])


def test_transfers_free_before_first_deadline(world, django_user_model):
    user = make_user(django_user_model, 1)
    squad = create_squad(user, "x", pick_squad())  # first gameweek = gw2, still open
    owned = list(squad.picks.values_list("player_id", flat=True))
    out = list(Player.objects.filter(pk__in=owned, position=F).values_list("pk", flat=True)[:3])
    inn = spare(squad, F, 3)
    assert [t.point_cost for t in make_transfers(squad, out, inn)] == [0, 0, 0]


def test_set_lineup_validation(world, django_user_model):
    squad = create_squad(make_user(django_user_model, 1), "x", pick_squad())
    players = list(Player.objects.filter(squad_picks__squad=squad))
    by_pos = {pos: [p.pk for p in players if p.position == pos] for pos in (G, DEF, F)}
    starters = by_pos[G][:1] + by_pos[DEF][:4] + by_pos[F][:6]
    bench = by_pos[G][1:] + by_pos[DEF][4:] + by_pos[F][6:]
    lineup = set_lineup(squad, starters, bench, starters[-1], starters[-2])
    assert lineup.captain_id == starters[-1]
    with pytest.raises(FantasyError, match="Starters need"):
        set_lineup(squad, by_pos[G] + by_pos[DEF][:4] + by_pos[F][:5], by_pos[DEF][4:] + by_pos[F][5:], starters[1], starters[2])
    with pytest.raises(FantasyError, match="must be starters"):
        set_lineup(squad, starters, bench, bench[0], starters[0])


# --------------------------------------------------------------------------- scoring


def _fixture(world, home, away, gw, finished=True, days_ago=1):
    return Fixture.objects.create(
        season=world["season"], gameweek=gw, liiga_id=Fixture.objects.count() + 1, home=home, away=away,
        starts_at=timezone.now() - timedelta(days=days_ago),
        status=Fixture.Status.FINISHED if finished else Fixture.Status.SCHEDULED,
    )


def _stat(player, fixture, points, played=True):
    PlayerGameStat.objects.create(player=player, fixture=fixture, points=points, stats={"played": played})


def test_captain_auto_sub_and_vice(world, django_user_model):
    user = make_user(django_user_model, 1)
    squad = make_squad_in_gw1(user, world)
    gw1 = world["gw1"]
    lineup = squad.lineups.get(gameweek=gw1)
    slots = list(lineup.slots.select_related("player"))
    starters = [s.player for s in slots if s.is_starter]
    bench = [s.player for s in slots if not s.is_starter]

    # Every team plays one finished game this gameweek.
    teams = world["teams"]
    fixtures = {t.pk: _fixture(world, teams[i], teams[i + 1], gw1) for i in range(0, 6, 2) for t in teams[i:i + 2]}
    for p in starters + bench:
        _stat(p, fixtures[p.team_id], D("2"))
    # Captain didn't play; first bench forward did.
    captain = lineup.captain
    PlayerGameStat.objects.filter(player=captain).update(points=0, stats={"played": False})
    bench_fwd = next(p for p in bench if p.position == captain.position)
    PlayerGameStat.objects.filter(player=bench_fwd).update(points=D("5"))

    gw1.status = Gameweek.Status.FINISHED
    gw1.save()
    assert score_gameweek(gw1) == 1
    score = GameweekScore.objects.get(squad=squad, gameweek=gw1)
    # 10 starters x 2, auto-sub 5, vice-captain doubled (+2).
    assert score.points == D("27")
    assert score.final
    assert any(d["auto_sub"] and d["player"] == bench_fwd.pk for d in score.detail)
    vice = next(d for d in score.detail if d["player"] == lineup.vice_captain_id)
    assert vice["multiplier"] == 2
    assert DailyScore.objects.get(squad=squad).points == D("27")
    squad.refresh_from_db()
    assert squad.total_points == D("27")
    assert squad.free_transfers == 2  # gained one when gw1 finished

    score_gameweek(gw1)  # idempotent
    squad.refresh_from_db()
    assert squad.total_points == D("27") and squad.free_transfers == 2


def test_no_auto_sub_while_team_still_to_play(world, django_user_model):
    squad = make_squad_in_gw1(make_user(django_user_model, 1), world)
    gw1 = world["gw1"]
    _fixture(world, world["teams"][0], world["teams"][1], gw1, finished=False, days_ago=-1)
    _fixture(world, world["teams"][2], world["teams"][3], gw1, finished=False, days_ago=-1)
    _fixture(world, world["teams"][4], world["teams"][5], gw1, finished=False, days_ago=-1)
    score_gameweek(gw1)
    score = GameweekScore.objects.get(squad=squad, gameweek=gw1)
    assert score.points == 0 and not score.final
    assert not any(d["auto_sub"] for d in score.detail)


# --------------------------------------------------------------------------- leaderboards


def test_leaderboard_scopes_and_ties(world, django_user_model):
    oulu = CommunityGroup.objects.create(name="Oulu", slug="oulu")
    users = [make_user(django_user_model, i) for i in range(3)]
    squads = [make_squad_in_gw1(u, world, name=f"S{i}") for i, u in enumerate(users)]
    Squad.objects.filter(pk=squads[0].pk).update(total_points=50)
    Squad.objects.filter(pk=squads[1].pk).update(total_points=50)
    Squad.objects.filter(pk=squads[2].pk).update(total_points=70)
    Membership.objects.create(user=users[0], community=oulu)
    Membership.objects.create(user=users[2], community=oulu)

    board = leaderboards.leaderboard(world["season"], "season", "global", user=users[1])
    assert [(r["rank"], r["points"]) for r in board["rows"]] == [(1, 70), (2, 50), (2, 50)]
    assert board["me"]["squad_name"] == "S1"

    local = leaderboards.leaderboard(world["season"], "season", "community", community="oulu")
    assert [r["squad_name"] for r in local["rows"]] == ["S2", "S0"]

    league = leaderboards.create_league(squads[0], "Friends")
    leaderboards.join_league(squads[1], league.code.lower())
    friends = leaderboards.leaderboard(world["season"], "season", "league", league=league)
    assert {r["squad_name"] for r in friends["rows"]} == {"S0", "S1"}

    GameweekScore.objects.create(squad=squads[1], gameweek=world["gw1"], total=12)
    week = leaderboards.leaderboard(world["season"], "week", gameweek=world["gw1"])
    assert week["rows"][0]["squad_name"] == "S1"
    today = timezone.localdate()
    DailyScore.objects.create(squad=squads[2], gameweek=world["gw1"], date=today, points=9)
    day = leaderboards.leaderboard(world["season"], "day", day=today)
    assert [r["squad_name"] for r in day["rows"]] == ["S2"]

    with pytest.raises(FantasyError):
        leaderboards.join_league(squads[2], "NOPE00")


# --------------------------------------------------------------------------- Liiga import


class FakeLiiga:
    def __init__(self, start):
        self.start = start

    def teams(self, season):
        return [{"id": "1:kärpät", "nameAbbreviation": "KÄR", "shortName": "Kärpät", "logos": {}},
                {"id": "2:kalpa", "nameAbbreviation": "KAL", "shortName": "KalPa", "logos": {}}]

    def games(self, season):
        team = lambda tid, name, goals: {"teamId": tid, "teamName": name, "goals": goals}
        return [
            {"id": 10, "serie": "RUNKOSARJA", "gameWeek": 8, "start": self.start, "started": True, "ended": True,
             "finishedType": "ENDED_DURING_REGULAR_GAME_TIME",
             "homeTeam": team("1:kärpät", "Kärpät", 2), "awayTeam": team("2:kalpa", "KalPa", 0)},
            {"id": 11, "serie": "PRACTICE", "gameWeek": 0, "start": self.start, "started": True, "ended": True,
             "homeTeam": team("1:kärpät", "Kärpät", 1), "awayTeam": team("2:kalpa", "KalPa", 1)},
        ]

    def roster(self, team_id, season):
        if team_id == "1:kärpät":
            return [{"id": 100, "firstName": "Aku", "lastName": "Forward", "role": "LEFT_WING"},
                    {"id": 101, "firstName": "Bo", "lastName": "Goalie", "role": "GOALIE"},
                    {"id": 102, "firstName": "Cy", "lastName": "Defence", "role": "RIGHT_DEFENSEMAN"}]
        return [{"id": 200, "firstName": "Dan", "lastName": "Away", "role": "CENTER"}]

    def game(self, season, game_id):
        return {"game": {"ended": True, "started": True, "finishedType": "ENDED_DURING_REGULAR_GAME_TIME",
                         "homeTeam": {"goals": 2}, "awayTeam": {"goals": 0}},
                "homeTeamPlayers": [], "awayTeamPlayers": []}

    def game_stats(self, season, game_id):
        skater = lambda pid, **kw: {"playerId": pid, "period": {"timeofice": 400, **kw}}
        goalie = lambda pid, saves: {"playerId": pid, "period": {"saves": saves, "goalsAllowed": 0}}
        period = lambda players, goalies: {"periodPlayerStats": players, "goaliePeriodStats": goalies}
        return {
            "homeTeam": [
                period([skater(100, goals=1, shots=2, plusminus=1, winningGoal=True), skater(102, assists=1)], [goalie(101, 8)]),
                period([skater(100, goals=1, shots=1, plusminus=1), skater(102)], [goalie(101, 9)]),
                period([skater(100), skater(102, blockedShots=3)], [goalie(101, 10)]),
            ],
            "awayTeam": [period([skater(200, plusminus=-1)], [])],
        }


def test_liiga_sync_end_to_end(db):
    oulu = CommunityGroup.objects.create(name="Oulu", slug="oulu")
    client = FakeLiiga(start=(timezone.now() - timedelta(hours=4)).isoformat())
    season = liiga.sync_schedule(client, 2027)
    assert season.is_current and season.fixtures.count() == 1  # practice game skipped
    assert Team.objects.get(liiga_id="1:kärpät").community == oulu
    assert liiga.sync_players(client, season) == 4
    assert Player.objects.get(liiga_id=101).position == G
    assert Player.objects.get(liiga_id=102).position == DEF

    fixture = season.fixtures.get()
    assert liiga.sync_fixture_stats(client, fixture) == 4
    fixture.refresh_from_db()
    assert fixture.stats_synced_at and fixture.home_goals == 2

    fwd = PlayerGameStat.objects.get(player__liiga_id=100)
    assert fwd.stats["goals"] == 2 and fwd.stats["toi"] == 1200
    assert fwd.breakdown == {"appearance": 1, "goals": 8, "winning_goal": 1, "full_shift": 1, "plus_minus": 2, "shots": 1}
    goalie = PlayerGameStat.objects.get(player__liiga_id=101)
    assert goalie.breakdown == {"appearance": 1, "saves": 5, "win": 3, "shutout": 5}
    defence = PlayerGameStat.objects.get(player__liiga_id=102)
    assert defence.breakdown["shutout"] == rules.DEFENCE_SHUTOUT_POINTS
    assert Player.objects.get(liiga_id=100).total_points == fwd.points

    liiga.refresh_gameweeks(season)
    assert season.gameweeks.get(number=8).status == Gameweek.Status.FINISHED


# --------------------------------------------------------------------------- API


def test_api_flow(world, django_user_model):
    api = APIClient()
    assert api.get("/api/fantasy/season/").data["next_deadline_gameweek"] == 2
    assert api.get("/api/fantasy/players/?position=G").data["count"] == 6

    user = make_user(django_user_model, 1)
    api.force_authenticate(user)
    assert api.get("/api/fantasy/squad/").status_code == 404
    res = api.post("/api/fantasy/squad/", {"name": "Kärpät Ultras", "player_ids": pick_squad()}, format="json")
    assert res.status_code == 201, res.data
    assert len(res.data["players"]) == 15

    lineup = api.get("/api/fantasy/squad/lineup/").data
    assert lineup["gameweek"] == 2 and len(lineup["starters"]) == 11
    res = api.put("/api/fantasy/squad/lineup/", {**lineup, "captain": lineup["starters"][3],
                                                 "vice_captain": lineup["starters"][4]}, format="json")
    assert res.status_code == 200, res.data

    owned = [p["id"] for p in api.get("/api/fantasy/squad/").data["players"]]
    out = next(p for p in owned if Player.objects.get(pk=p).position == F)
    inn = spare(Squad.objects.get(user=user), F, 1)[0]
    res = api.post("/api/fantasy/squad/transfers/", {"out": [out], "in": [inn]}, format="json")
    assert res.status_code == 201, res.data

    league = api.post("/api/fantasy/leagues/", {"name": "Office"}, format="json")
    assert league.status_code == 201 and len(league.data["code"]) == 6
    board = api.get(f"/api/fantasy/leaderboard/?scope=league&league={league.data['id']}").data
    assert board["me"]["squad_name"] == "Kärpät Ultras"
    assert api.get("/api/fantasy/leaderboard/?period=week").status_code == 400  # needs gameweek


def test_dev_auth_bypass_only_in_debug(world, django_user_model, settings):
    admin = django_user_model.objects.create_superuser(email="boss@example.com", password="x-pass-123")
    create_squad(admin, "Boss XI", pick_squad())
    api = APIClient()
    settings.DEBUG = False
    assert api.get("/api/fantasy/squad/").status_code in (401, 403)
    settings.DEBUG = True
    assert api.get("/api/fantasy/squad/").data["name"] == "Boss XI"
    assert api.get("/api/fantasy/squad/?as=nobody@example.com").status_code in (401, 403)
