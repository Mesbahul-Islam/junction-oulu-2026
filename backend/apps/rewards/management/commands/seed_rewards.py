"""Demo partners and perks, plus sample contribution statistics for the demo members (local dev only).

The statistics go through services.ingest, the same path POST /api/rewards/stats/ uses. Safe to run again.

    manage.py seed_rewards
"""

from django.core.management.base import BaseCommand

from apps.rewards.models import Partner, Perk
from apps.rewards.services import ingest

# (name, slug, category, where, what the discount is on, terms, % off at Contributor / Local guide / Trusted voice, stock)
# 0 = not offered at that level, 100 = free. Logos: frontend/public/partners/<slug>.webp
PARTNERS = [
    ("Prisma", "prisma", "Food", "Oulu", "groceries", "In store, show the code at the till.", (5, 8, 10), None),
    ("Hesburger", "hesburger", "Food", "Oulu", "meals", "Any Oulu restaurant, once a month.", (15, 25, 40), None),
    ("Tokmanni", "tokmanni", "Shopping", "Oulu", "home and everyday items", "In store, show the code at the till.", (5, 10, 15), None),
    ("Verkkokauppa.com", "verkkokauppa", "Shopping", "Online", "electronics", "Enter the code at checkout.", (5, 8, 12), None),
    ("Marimekko", "marimekko", "Shopping", "Online", "clothing and homeware", "Not on sale items.", (0, 10, 15), None),
    ("DNA", "dna", "Phone & internet", "Online", "mobile and broadband plans", "For the first 6 months.", (10, 20, 30), None),
    ("PowerPark", "powerpark", "Leisure & travel", "Alahärmä", "day passes", "Show the code at the gate.", (0, 25, 50), 30),
    ("Finnair", "finnair", "Leisure & travel", "Online", "flights within Finland", "Book online with the code.", (0, 10, 20), 20),
]

# Members at different levels, so every state of the rewards page can be shown.
DEMO_STATS = [
    {"email": "maria@example.com", "contributions": {"posts_approved": 9, "photos_approved": 4, "corrections_accepted": 3},
     "community_rating": {"average": 4.8, "count": 26}, "trusted_voice": True, "trust_score": 74},
    {"email": "aino@example.com", "contributions": {"posts_approved": 6, "photos_approved": 2, "corrections_accepted": 1},
     "community_rating": {"average": 4.4, "count": 12}, "trust_score": 55},
    {"email": "newcomer@example.com", "contributions": {"posts_approved": 3, "photos_approved": 1, "rejected": 1},
     "community_rating": {"average": 4.2, "count": 4}, "trust_score": 18},
    {"email": "iryna@example.com", "contributions": {"posts_approved": 1},
     "community_rating": {"average": 5.0, "count": 1}, "trust_score": 6},
]


class Command(BaseCommand):
    help = "Create demo reward partners and perks, and send sample contribution statistics"

    def handle(self, *args, **opts):
        for name, slug, category, city, title, terms, (c, g, t), stock in PARTNERS:
            partner, _ = Partner.objects.update_or_create(slug=slug, defaults={"name": name, "category": category, "city": city})
            Perk.objects.update_or_create(partner=partner, defaults={
                "title": title, "terms": terms, "off_contributor": c, "off_local_guide": g, "off_trusted": t,
                "stock": stock, "active": True})
        # Partners no longer in the list stay in the database (old codes point to them) but stop showing.
        Perk.objects.exclude(partner__slug__in=[p[1] for p in PARTNERS]).update(active=False)
        rows = [{"period": "2026-10", **row, "_raw": row} for row in DEMO_STATS]
        result = ingest(rows, source="seed_rewards")
        self.stdout.write(self.style.SUCCESS(
            f"{Perk.objects.filter(active=True).count()} active partners, "
            f"stats for {len(result['stored'])} members ({len(result['skipped'])} not found)."))
