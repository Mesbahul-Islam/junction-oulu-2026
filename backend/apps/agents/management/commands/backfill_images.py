"""Fetch the lead picture for stored articles that don't have one yet (e.g. stories made before
pictures were supported). New runs get pictures automatically from the wire desk.

Usage: python manage.py backfill_images [--all] [--refetch]
  (default: only articles that became stories; --refetch also redoes ones that already have a picture)
"""

from django.core.management.base import BaseCommand

from apps.agents.newsroom.wire import page_image
from apps.feed.models import SourceDocument


class Command(BaseCommand):
    help = "Fetch missing article pictures (og:image of the article page)."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Every stored article, not just those with a story")
        parser.add_argument("--refetch", action="store_true",
                            help="Fetch again even if a picture is stored (repairs links saved before the &center fix)")

    def handle(self, *args, all, refetch, **options):
        docs = SourceDocument.objects.all() if refetch else SourceDocument.objects.filter(image_url="")
        if not all:
            docs = docs.filter(snippets__isnull=False).distinct()
        found = total = 0
        for doc in docs:
            total += 1
            if image := page_image(doc.url):
                SourceDocument.objects.filter(pk=doc.pk).update(image_url=image)
                found += 1
        self.stdout.write(self.style.SUCCESS(f"Pictures found for {found} of {total} articles."))
