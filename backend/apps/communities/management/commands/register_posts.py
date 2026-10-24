"""Backfill Community News posts: detect language, pass questions to the newsroom,
and (re)translate them. Safe to re-run; existing translations are kept.

    python manage.py register_posts
"""

from django.core.management.base import BaseCommand

from apps.communities import services
from apps.communities.models import Post


class Command(BaseCommand):
    help = "Detect language, link questions to the newsroom and translate existing community posts."

    def handle(self, *args, **options):
        posts = Post.objects.exclude(status=Post.Status.REMOVED).select_related("community", "author")
        for post in posts:
            services.register_post(post)
        self.stdout.write(self.style.SUCCESS(f"Registered {posts.count()} posts (translations run in the background)."))
