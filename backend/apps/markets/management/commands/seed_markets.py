"""Seed demo Liiga ice hockey events with a binary market and a fantasy contest.

Virtual points only. Player names are fictional demo data.
"""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.markets.models import EventMarket, FantasyContest, Player, SportEvent
from apps.markets.services.ledger import get_house_wallet

EVENTS = [
    ("Kärpät", "Tappara", 2),
    ("Ässät", "Lukko", 4),
]

# (name, team, position, salary) — fictional players for the demo.
PLAYERS = [
    ("Aleksi Niemelä", "Kärpät", "F", "9.5"),
    ("Joonas Kyllönen", "Kärpät", "F", "8.0"),
    ("Eetu Rautio", "Kärpät", "F", "6.5"),
    ("Mikko Haapala", "Kärpät", "D", "7.0"),
    ("Ville Karjalainen", "Kärpät", "D", "5.5"),
    ("Juuso Pesonen", "Kärpät", "G", "8.5"),
    ("Lauri Mäkinen", "Tappara", "F", "10.0"),
    ("Otto Lehtonen", "Tappara", "F", "7.5"),
    ("Santeri Virta", "Tappara", "F", "6.0"),
    ("Tuomas Heikkilä", "Tappara", "D", "6.5"),
    ("Niko Salmi", "Tappara", "D", "5.0"),
    ("Henri Ojala", "Tappara", "G", "9.0"),
]


class Command(BaseCommand):
    help = "Seed demo Liiga events, binary markets and a fantasy contest (virtual points only)."

    @transaction.atomic
    def handle(self, *args, **options):
        get_house_wallet()
        now = timezone.now()
        players = []
        for name, team, pos, salary in PLAYERS:
            player, _ = Player.objects.update_or_create(
                name=name, team=team,
                defaults={"position": pos, "salary": Decimal(salary), "sport": "ice_hockey"},
            )
            players.append(player)

        for home, away, days in EVENTS:
            event, _ = SportEvent.objects.get_or_create(
                home=home, away=away, league="Liiga",
                defaults={"sport": "ice_hockey", "starts_at": (now + timedelta(days=days)).replace(
                    hour=18, minute=30, second=0, microsecond=0)},
            )
            EventMarket.objects.get_or_create(
                event=event, kind=EventMarket.Kind.BINARY, question=f"Will {home} beat {away}?",
                defaults={"rule": EventMarket.Rule.HOME_WIN},
            )
            EventMarket.objects.get_or_create(
                event=event, kind=EventMarket.Kind.BINARY,
                question=f"Will {home} vs. {away} have more than 5.5 goals?",
                defaults={"rule": EventMarket.Rule.TOTAL_OVER, "line": Decimal("5.5")},
            )
            pool = [p for p in players if p.team in (home, away)]
            if pool:
                market, _ = EventMarket.objects.get_or_create(
                    event=event, kind=EventMarket.Kind.FANTASY,
                    question=f"Fantasy: {home} vs. {away}",
                )
                contest, _ = FantasyContest.objects.get_or_create(
                    market=market,
                    defaults={
                        "salary_cap": Decimal("45.00"),
                        "roster_size": 6,
                        "entry_fee": Decimal("50.00"),
                        "prize_structure": [0.5, 0.3, 0.2],
                    },
                )
                contest.player_pool.set(pool)
            self.stdout.write(self.style.SUCCESS(f"Seeded {event}"))
