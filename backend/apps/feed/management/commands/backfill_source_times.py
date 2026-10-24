"""Give stored Kaleva articles their publication time, and published stories that time.

Articles fetched before ``SourceDocument.published_at`` existed have none, so their stories
show when the editor clicked publish. The time comes from the RSS feed while the article is
still in it, else from the article page's datePublished. Safe to run again.
"""

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from apps.agents.newsroom import kaleva, wire
from apps.editorial.services import source_time
from apps.feed.models import SourceDocument, Snippet
from apps.common.choices import ReviewStatus


def page_time(url):
    import httpx

    if not kaleva.allowed(url):
        return None
    try:
        resp = httpx.get(url, timeout=kaleva.TIMEOUT, follow_redirects=True, headers={"User-Agent": wire.USER_AGENT})
        resp.raise_for_status()
    except Exception:
        return None
    return parse_datetime(kaleva.extract(resp.text)["published"] or "")


class Command(BaseCommand):
    help = "Fill in Kaleva publication times for stored articles and published stories."

    def handle(self, *args, **options):
        try:
            from_feed = {e["url"]: e["published_at"] for e in wire.fetch_entries(wire.KALEVA_FEED_URL)}
        except Exception:
            from_feed = {}
        docs = SourceDocument.objects.filter(published_at__isnull=True, snippets__isnull=False).distinct()
        filled = 0
        for doc in docs:
            when = from_feed.get(doc.url) or page_time(doc.url)
            if when:
                SourceDocument.objects.filter(url=doc.url, published_at__isnull=True).update(published_at=when)
                filled += 1
        moved = 0
        for snippet in Snippet.objects.filter(review_status=ReviewStatus.PUBLISHED).prefetch_related("source_documents"):
            when = source_time(snippet)
            if when and when != snippet.published_at:
                Snippet.objects.filter(pk=snippet.pk).update(published_at=when)
                moved += 1
        self.stdout.write(f"{filled} of {docs.count()} articles got a time; {moved} stories now show Kaleva's time.")
