"""Brand partners and their prizes for the demo, plus vouchers for gameweeks already played.

The brands are examples for this prototype (logos in backend/media/fantasy/). Prize values are
illustrative. Safe to run again: sponsors and prizes are updated in place, vouchers are not duplicated.

    manage.py seed_sponsors
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.fantasy.models import Gameweek, Player, Reward, Sponsor
from apps.fantasy.services.rewards import award_gameweek, brand_image
from apps.fantasy.services.squads import current_season

SOURCE = Path(settings.MEDIA_ROOT) / "fantasy"  # original files, if present locally
# Web-sized copies kept in the repo, used when the originals aren't there (fresh clones).
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "brands"


def source_for(filename: str, slug: str) -> Path | None:
    for path in (SOURCE / filename, ASSETS / f"{slug}.webp"):
        if path.exists():
            return path
    return None

# slug: (name, source file, tagline, website)
SPONSORS = {
    "prisma": ("Prisma", "primsa.png", "Gameweek prizes", "https://www.prisma.fi"),
    "hesburger": ("Hesburger", "hesburger.png", "Oulu weekly prizes", "https://www.hesburger.fi"),
    "tokmanni": ("Tokmanni", "tokmanni.png", "Top 10 every gameweek", "https://www.tokmanni.fi"),
    "verkkokauppa": ("Verkkokauppa.com", "verkkokauppa.png", "Season champion", "https://www.verkkokauppa.com"),
    "powerpark": ("PowerPark", "powerpark.png", "Oulu season prize", "https://www.powerpark.fi"),
    "dna": ("DNA", "dna.png", "Weekly prizes", "https://www.dna.fi"),
    "finnair": ("Finnair", "finnair.png", "Season champion", "https://www.finnair.com"),
    "marimekko": ("Marimekko", "marimekko.png", "Oulu season prizes", "https://www.marimekko.com"),
}

# Each brand sets its own prize. Leaderboard prizes go to the top 3 only.
# (sponsor, kind, title, description, period, scope, community, rank_from, rank_to, threshold, tier, title_fi, description_fi)
REWARDS = [
    ("prisma", "rank", "50 € gift card", "Win the gameweek in Finland", "week", "global", "", 1, 1, None, "",
     "50 € lahjakortti", "Voita kierros Suomessa"),
    ("prisma", "rank", "20 € gift card", "Finish 2nd or 3rd in the gameweek", "week", "global", "", 2, 3, None, "",
     "20 € lahjakortti", "Sijoitu kierroksella 2. tai 3."),
    ("tokmanni", "rank", "15 € voucher", "Top 3 in Oulu in the gameweek", "week", "community", "oulu", 1, 3, None, "",
     "15 € lahjakortti", "Kolmen parhaan joukkoon Oulussa kierroksella"),
    ("hesburger", "player", "Meal for two", "", "week", "global", "", 1, 1, 5, "", "Ateria kahdelle", ""),
    ("dna", "points", "1 month of DNA TV", "Score 115 points or more in a gameweek", "week", "global", "", 1, 1, 115, "",
     "DNA TV kuukaudeksi", "Tee kierroksella vähintään 115 pistettä"),
    ("finnair", "rank", "Two return flights in Finland", "Season champion in Finland", "season", "global", "", 1, 1, None, "",
     "Kaksi meno-paluulentoa Suomessa", "Kauden mestari Suomessa"),
    ("verkkokauppa", "rank", "200 € gift card", "2nd or 3rd in Finland at the end of the season", "season", "global", "", 2, 3, None, "",
     "200 € lahjakortti", "Kauden 2. tai 3. Suomessa"),
    ("powerpark", "rank", "Family day pass", "Top 3 in Oulu at the end of the season", "season", "community", "oulu", 1, 3, None, "",
     "Perheen päivälippu", "Kolmen parhaan joukkoon Oulussa kauden lopussa"),
    ("marimekko", "tier", "20 € gift card", "Finish the season in Gold or Diamond", "season", "global", "", 1, 1, None, "gold",
     "20 € lahjakortti", "Päätä kausi kulta- tai timanttitasolla"),
]


class Command(BaseCommand):
    help = "Create demo brand partners, their prizes, and vouchers for finished gameweeks"

    def handle(self, *args, **opts):
        season = current_season()
        sponsors = {}
        for slug, (name, filename, tagline, website) in SPONSORS.items():
            source = source_for(filename, slug)
            if source is None:
                raise CommandError(f"Missing brand image for {name}")
            sponsors[slug], _ = Sponsor.objects.update_or_create(
                slug=slug, defaults={"name": name, "logo": brand_image(source, slug), "tagline": tagline, "website": website},
            )
        # Hesburger's pick: Kärpät's top fantasy scorer (the brand would choose; this stands in for that).
        pick = Player.objects.filter(team__name="Kärpät", active=True).exclude(position="G").order_by("-total_points").first()
        kept = []
        for (slug, kind, title, description, period, scope, community, rank_from, rank_to, threshold, tier,
             title_fi, description_fi) in REWARDS:
            player = pick if kind == "player" else None
            if kind == "player":
                if player is None:
                    continue
                description = f"Have {player.name} in your lineup. If he scores {threshold}+ points in the gameweek, you win."
                description_fi = f"Ota {player.name} kokoonpanoosi. Jos hän tekee kierroksella vähintään {threshold} pistettä, voitat."
            reward, _ = Reward.objects.update_or_create(
                sponsor=sponsors[slug], season=season, period=period, kind=kind, scope=scope, rank_from=rank_from,
                defaults={"title": title, "description": description, "community_slug": community, "rank_to": rank_to,
                          "threshold": threshold, "tier": tier, "player": player, "active": True,
                          "title_fi": title_fi, "description_fi": description_fi},
            )
            kept.append(reward.pk)
        # Prizes no longer in the list are switched off, not deleted (vouchers already won stay valid).
        Reward.objects.filter(season=season).exclude(pk__in=kept).update(active=False)
        # The Lämäri artwork used as the fantasy theme (web-sized copies).
        for filename, slug in (("lamari.png", "lamari"), ("icehockeyplayer2.png", "player-skate"), ("hockeyplayer1.png", "player-splash")):
            if source := source_for(filename, slug):
                brand_image(source, slug, max_side=900)

        vouchers = sum(award_gameweek(gw) for gw in Gameweek.objects.filter(season=season, status=Gameweek.Status.FINISHED))
        self.stdout.write(self.style.SUCCESS(
            f"{len(sponsors)} brand partners, {len(REWARDS)} prizes, {vouchers} new vouchers for finished gameweeks"
        ))
