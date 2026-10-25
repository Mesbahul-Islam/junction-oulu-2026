"""Demo partners and perks (local dev only). Members' levels come from trust (seed_trust_demo). Safe to run again.

    manage.py seed_rewards
"""

from django.core.management.base import BaseCommand

from apps.rewards.models import Partner, Perk

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

class Command(BaseCommand):
    help = "Create demo reward partners and perks"

    def handle(self, *args, **opts):
        for name, slug, category, city, title, terms, (c, g, t), stock in PARTNERS:
            partner, _ = Partner.objects.update_or_create(slug=slug, defaults={"name": name, "category": category, "city": city})
            Perk.objects.update_or_create(partner=partner, defaults={
                "title": title, "terms": terms, "off_contributor": c, "off_local_guide": g, "off_trusted": t,
                "stock": stock, "active": True})
        # Partners no longer in the list stay in the database (old codes point to them) but stop showing.
        Perk.objects.exclude(partner__slug__in=[p[1] for p in PARTNERS]).update(active=False)
        self.stdout.write(self.style.SUCCESS(f"{Perk.objects.filter(active=True).count()} active partners."))
