"""Demo managers with squads since gameweek 1, scored on real Liiga stats.

Run after `sync_liiga`. Creates ~30 managers (some Oulu members who favour
Kärpät players), two private leagues, and moves the dev admin's squad (if any)
to gameweek 1 so it shows up on every leaderboard. Re-running replaces the
demo managers. Local dev / demo only.

    manage.py seed_fantasy_demo [--managers 30] [--seed 2026]
"""

import random
from collections import Counter
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.communities.models import CommunityGroup, Membership
from apps.fantasy import rules
from apps.fantasy.models import Gameweek, League, Player, Squad, SquadPick
from apps.fantasy.services.leaderboards import create_league
from apps.fantasy.services.scoring import score_gameweek
from apps.fantasy.services.squads import _write_lineup, current_season, default_lineup_order

DEMO_DOMAIN = "demo.fantasy"
DEMO_PASSWORD = "demo1234"
NAMES = [
    "Aino", "Eetu", "Veera", "Onni", "Sofia", "Leevi", "Ella", "Elias", "Aada", "Väinö", "Helmi", "Niilo",
    "Priya", "Oleksandr", "Fatima", "Kenji", "Amara", "Lucas", "Mariam", "Dmytro", "Sanna", "Joonas",
    "Iida", "Kalle", "Noora", "Tuomas", "Minna", "Ahmed", "Lin", "Rasmus", "Elsa", "Mikael",
]
TEAM_NAMES = [
    "Puck Dynasty", "Raksila Rockets", "Toppilan Tähdet", "Ylläs Yetis", "Haukipudas Hurricanes",
    "Kiiminki Kings", "Nallikari Nordics", "Pörssi Pirates", "Tuira Thunder", "Kaukovainio Komets",
    "Jääkiekko Jedi", "Sauna Snipers", "Pohjoisen Pantterit", "Oulujoki Otters", "Hiukat Hockey",
    "Five Hole FC", "Blue Line Boys", "Maila Mafia", "Kärpät Ultras", "Ice Cold Takes",
    "Rinkside Rebels", "Slapshot Society", "Overtime Oulu", "Zamboni Drivers", "Penalty Box",
    "Hat Trick Heroes", "Power Play Pros", "Top Shelf", "Neutral Zone", "Empty Netters",
]


def random_squad(rng: random.Random, pool: list[Player], budget: Decimal, favourite_team_id=None) -> list[Player]:
    """A valid squad: points-weighted random picks, budget-aware, optional favourite team."""
    for _ in range(200):
        need = dict(rules.SQUAD_COMPOSITION)
        per_team, picked, spent = Counter(), [], Decimal(0)
        candidates = pool[:]
        rng.shuffle(candidates)
        weight = lambda p: float(p.total_points) + 5 + (40 if p.team_id == favourite_team_id else 0)
        candidates.sort(key=lambda p: -weight(p) * rng.random())
        for p in candidates:
            if not need[p.position] or per_team[p.team_id] >= rules.MAX_PER_TEAM:
                continue
            left = sum(need.values()) - 1
            if spent + p.price + left * rules.MIN_PRICE > budget:
                continue
            picked.append(p)
            need[p.position] -= 1
            per_team[p.team_id] += 1
            spent += p.price
            if not any(need.values()):
                return picked
    raise CommandError("Couldn't build a valid squad; is the player pool synced?")


class Command(BaseCommand):
    help = "Create demo fantasy managers, leagues and scores from real Liiga stats"

    def add_arguments(self, parser):
        parser.add_argument("--managers", type=int, default=30)
        parser.add_argument("--seed", type=int, default=2026)

    def handle(self, *args, managers, seed, **opts):
        rng = random.Random(seed)
        season = current_season()
        gameweeks = list(season.gameweeks.exclude(status=Gameweek.Status.UPCOMING).order_by("number"))
        if not gameweeks:
            raise CommandError("No played gameweeks yet. Run `manage.py sync_liiga` first.")
        first = gameweeks[0]
        pool = list(Player.objects.filter(active=True, team__isnull=False).select_related("team"))
        oulu = CommunityGroup.objects.filter(slug="oulu").first()
        karpat = oulu.fantasy_teams.first() if oulu else None
        User = get_user_model()

        with transaction.atomic():
            User.objects.filter(email__endswith=f"@{DEMO_DOMAIN}").delete()
            squads = []
            for i in range(managers):
                name = NAMES[i % len(NAMES)]
                user = User.objects.create_user(
                    email=f"{name.lower()}{i + 1}@{DEMO_DOMAIN}", password=DEMO_PASSWORD, display_name=name
                )
                local = oulu is not None and rng.random() < 0.45
                if local:
                    Membership.objects.create(user=user, community=oulu)
                players = random_squad(rng, pool, season.budget, karpat.pk if (local and karpat) else None)
                squad = Squad.objects.create(
                    user=user, season=season, name=TEAM_NAMES[i % len(TEAM_NAMES)],
                    bank=season.budget - sum((p.price for p in players), Decimal(0)), first_gameweek=first,
                )
                SquadPick.objects.bulk_create(SquadPick(squad=squad, player=p, purchase_price=p.price) for p in players)
                ordered = default_lineup_order(players)
                # Managers rotate their captain between their best starters each week.
                for gw in gameweeks:
                    captain, vice = rng.sample(ordered[:6], 2)
                    _write_lineup(squad, gw, ordered, captain, vice)
                squads.append(squad)

            # The dev admin joins in from gameweek 1 so they're on every leaderboard.
            admin_squad = Squad.objects.filter(season=season, user__is_superuser=True).select_related("user").first()
            if admin_squad:
                lineup = admin_squad.lineups.order_by("gameweek__number").first()
                admin_squad.first_gameweek = first
                admin_squad.save(update_fields=["first_gameweek", "updated_at"])
                if lineup and lineup.gameweek.number > first.number:
                    ordered = [s.player for s in lineup.slots.all()]
                    for gw in gameweeks:
                        _write_lineup(admin_squad, gw, ordered, lineup.captain, lineup.vice_captain)
                if oulu:
                    Membership.objects.get_or_create(user=admin_squad.user, community=oulu)

            League.objects.filter(season=season, name__in=["Technopolis Hackers", "Kärpät Fans Oulu"]).delete()
            hackers = create_league(admin_squad or squads[0], "Technopolis Hackers")
            hackers.members.add(*squads[:8])
            locals_ = [s for s in squads if oulu and Membership.objects.filter(user=s.user, community=oulu).exists()]
            fans = create_league(locals_[0] if locals_ else squads[0], "Kärpät Fans Oulu")
            fans.members.add(*locals_)

        for gw in gameweeks:
            score_gameweek(gw)

        top = Squad.objects.filter(season=season).order_by("-total_points").first()
        self.stdout.write(f"{managers} demo managers (password {DEMO_PASSWORD!r}), {len(locals_)} in Oulu")
        self.stdout.write(f"Scored gameweeks {first.number}-{gameweeks[-1].number}; leader: {top} ({top.total_points} pts)")
        self.stdout.write(f"Leagues: {hackers.name} code {hackers.code}, {fans.name} code {fans.code}")
        self.stdout.write(self.style.SUCCESS("Done"))
