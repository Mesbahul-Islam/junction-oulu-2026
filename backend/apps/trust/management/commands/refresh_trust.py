"""Recompute every member's trust score (scores also update on their own as members act)."""

from django.core.management.base import BaseCommand

from apps.trust.services import refresh_all


class Command(BaseCommand):
    help = "Recompute trust scores for every community member"

    def handle(self, *args, **opts):
        self.stdout.write(self.style.SUCCESS(f"Refreshed {refresh_all()} memberships"))
