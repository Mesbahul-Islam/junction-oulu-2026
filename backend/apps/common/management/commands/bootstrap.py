"""One command to get a working dev database: migrate, seed, create an admin.

Safe to run repeatedly (every step is idempotent). Docker runs it on every
`docker compose up` via the one-shot `setup` service.
"""

import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand


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
        self.stdout.write(self.style.SUCCESS("Bootstrap complete."))

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
