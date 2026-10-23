"""One command to get a working dev database: migrate, seed, create an admin.

Safe to run repeatedly (every step is idempotent). Docker runs it on every
`docker compose up` via the one-shot `setup` service.
"""

import datetime
import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

# Local demo accounts (also listed in docs/GUIDE.md). Never use these anywhere shared.
DEMO_READER_PASSWORD = "demo-reader"
DEMO_READERS = [
    # email, situation, language, interest slugs, days since arrival in Finland
    ("newcomer@example.com", "newcomer", "uk", ["housing", "work", "health", "services"], 5),
    ("fan@example.com", "resident", "fi", ["sports", "culture", "events"], None),
]


class Command(BaseCommand):
    help = "Migrate, load demo data and create the dev admin user (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--no-seed", action="store_true", help="Only migrate and create the admin.")

    def handle(self, *args, no_seed=False, **options):
        call_command("migrate", interactive=False, verbosity=1)
        if not no_seed:
            call_command("seed_demo")
            call_command("seed_markets")
        self._ensure_admin()
        if not no_seed:
            self._ensure_demo_readers()
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))

    def _ensure_demo_readers(self):
        """Two readers with opposite profiles, to compare personalised feeds (local dev only)."""
        from apps.accounts.models import Interest
        from apps.communities.models import CommunityGroup, Membership

        User = get_user_model()
        oulu = CommunityGroup.objects.filter(slug="oulu").first()
        for email, situation, language, interests, days in DEMO_READERS:
            if User.objects.filter(email=email).exists():
                continue
            user = User.objects.create_user(
                email=email, password=DEMO_READER_PASSWORD, reader_situation=situation, preferred_language=language,
                arrival_date=datetime.date.today() - datetime.timedelta(days=days) if days is not None else None,
                onboarded=True,
            )
            user.profile.interests.set(Interest.objects.filter(slug__in=interests))
            if oulu:
                Membership.objects.get_or_create(user=user, community=oulu)
            self.stdout.write(f"Created demo reader {email}.")

    def _ensure_admin(self):
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL")
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD")
        if not email or not password:
            self.stdout.write("DJANGO_SUPERUSER_EMAIL/PASSWORD not set; skipping admin user.")
            return
        User = get_user_model()
        if User.objects.filter(email=email).exists():
            self.stdout.write(f"Admin {email} already exists.")
            return
        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(self.style.SUCCESS(f"Created admin {email}."))
