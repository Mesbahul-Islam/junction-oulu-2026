"""One command to get a working dev database: migrate, seed, create an admin.

Safe to run repeatedly. Docker runs it on every `docker compose up` via the
one-shot `setup` service, before web/worker/beat start. Order:

1. migrate
2. seed_demo, seed_markets (fast, idempotent)
3. admin user, demo readers
4. Fantasy Liiga, first start only: sync_liiga (real season data from the Liiga
   API) then seed_fantasy_demo. Skipped once fantasy data exists, so restarts stay
   fast; a Liiga API failure is reported but doesn't stop the app from starting.
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


DEMO_POSTS = [
    ("fan@example.com", "Kärpät home game on Saturday: the 18:30 bus 3 from the centre gets very full, take the 18:10 one."),
    ("newcomer@example.com", "Does anyone know where to get a library card in Oulu? I arrived last week. Thanks!"),
    ("fan@example.com", "Ice on the Toppilansalmi walking path this morning, careful with strollers and bikes."),
    ("newcomer@example.com", "Ukrainian-speaking parents in Oulu: we meet at the main library on Sundays at 12, everyone welcome."),
]


class Command(BaseCommand):
    help = "Migrate, load demo data and create the dev admin user (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--no-seed", action="store_true", help="Only migrate and create the admin.")
        parser.add_argument("--no-fantasy", action="store_true", help="Skip the Liiga sync and fantasy demo data.")

    def handle(self, *args, no_seed=False, no_fantasy=False, **options):
        call_command("migrate", interactive=False, verbosity=1)
        if not no_seed:
            call_command("seed_demo")
            call_command("seed_markets")
        self._ensure_admin()
        if not no_seed:
            self._ensure_demo_readers()
            self._ensure_demo_posts()
            if not no_fantasy and os.environ.get("SEED_FANTASY", "true").lower() not in ("0", "false", "no"):
                self._ensure_fantasy()
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))

    def _ensure_fantasy(self):
        """First start only: import the Liiga season, then create demo managers and leagues."""
        from apps.fantasy.models import Player, Squad

        if Squad.objects.exists():
            self.stdout.write("Fantasy data already present; skipping Liiga sync (run `manage.py sync_liiga` to update).")
            return
        try:
            if not Player.objects.exists():
                self.stdout.write("Importing the Liiga season (first start, needs internet)...")
                call_command("sync_liiga")
            call_command("seed_fantasy_demo")
        except Exception as exc:  # network down, Liiga API changed ...: the rest of the app still starts
            self.stdout.write(self.style.WARNING(
                f"Fantasy seed skipped: {type(exc).__name__}: {exc}\n"
                "Run later: docker compose exec web python manage.py sync_liiga && "
                "docker compose exec web python manage.py seed_fantasy_demo"))

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

    def _ensure_demo_posts(self):
        """A few member posts so the app's Community News tab isn't empty on a fresh database."""
        from apps.communities.models import CommunityGroup, Post

        oulu = CommunityGroup.objects.filter(slug="oulu").first()
        User = get_user_model()
        authors = {u.email: u for u in User.objects.filter(email__in=[r[0] for r in DEMO_READERS])}
        if not oulu or len(authors) < 2 or Post.objects.filter(community=oulu).exists():
            return
        from apps.communities.services import register_post

        for email, body in DEMO_POSTS:
            register_post(Post.objects.create(community=oulu, author=authors[email], body=body))
        self.stdout.write(f"Created {len(DEMO_POSTS)} demo community posts.")

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
