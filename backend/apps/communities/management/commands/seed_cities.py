"""Seed the demo newsroom cities besides Oulu, their communities, neighbours and posts (idempotent).

    manage.py seed_cities

Runs on every start through ``bootstrap``. Data: ``apps/communities/demo_cities.py``.
"""

import datetime

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Interest, Location
from apps.communities import demo_cities as demo
from apps.communities.models import CommunityGroup, Membership, Post

DEMO_PASSWORD = "demo-reader"


class Command(BaseCommand):
    help = "Seed demo newsroom cities (Kemi, Raahe, Kajaani, Kittilä) with communities and posts"

    def handle(self, *args, **options):
        from apps.agents.services import add_city
        from apps.communities.services import register_post

        cities = {}
        for code, slug, name, description in demo.CITIES:
            city = (CommunityGroup.objects.filter(slug=slug).first()
                    or CommunityGroup.objects.filter(kind=CommunityGroup.Kind.GEO, municipality__iexact=name).first())
            if city is None:
                city = add_city(code)
                city.slug = slug
                city.save(update_fields=["slug", "updated_at"])
            if city.description != description:
                city.description = description
                city.save(update_fields=["description", "updated_at"])
            cities[slug] = city

        groups = dict(cities)
        for city_slug, slug, name, description, audiences, interests, languages in demo.TOPICS:
            group, created = CommunityGroup.objects.get_or_create(slug=slug, defaults={
                "name": name, "kind": CommunityGroup.Kind.TOPIC, "municipality": cities[city_slug].municipality,
                "description": description, "audiences": audiences, "languages": languages})
            if created:
                group.interests.set(Interest.objects.filter(slug__in=interests))
            groups[slug] = group

        User = get_user_model()
        for email, display_name, language, situation, city_slug, slugs in demo.NEIGHBOURS:
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User.objects.create_user(email=email, password=DEMO_PASSWORD, display_name=display_name,
                                                preferred_language=language, reader_situation=situation, onboarded=True)
            town = cities[city_slug].municipality
            if user.profile.location is None:
                user.profile.location = (Location.objects.filter(municipality=town, postal_code="", lat=None, lng=None).first()
                                         or Location.objects.create(name=town, municipality=town))
                user.profile.save()
            for slug in [city_slug, *slugs]:
                Membership.objects.get_or_create(user=user, community=groups[slug])

        authors = {u.email: u for u in User.objects.filter(email__in={email for email, _, _ in demo.POSTS})}
        created = 0
        for email, slug, body in demo.POSTS:
            if Post.objects.filter(community=groups[slug], body=body).exists():
                continue
            # Each neighbour writes in their own language; short posts are too short to guess reliably.
            register_post(Post.objects.create(community=groups[slug], author=authors[email], body=body),
                          language=authors[email].preferred_language)
            created += 1
        if created:
            # Spread each city's posts over the last two days, newest first, so the boards look lived in.
            now, seen = timezone.now(), {}
            for email, slug, body in demo.POSTS:
                city = groups[slug].municipality
                i = seen[city] = seen.get(city, -1) + 1
                Post.objects.filter(community=groups[slug], author__email=email, body=body).update(
                    created_at=now - datetime.timedelta(hours=1.5 + 4 * i))
        self.stdout.write(self.style.SUCCESS(
            f"Cities: {', '.join(c.name for c in cities.values())}; "
            f"{len(demo.TOPICS)} topic communities; {created} new posts."))
