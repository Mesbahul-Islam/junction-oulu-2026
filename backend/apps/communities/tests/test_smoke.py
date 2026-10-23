from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.communities import services
from apps.communities.models import CommunityGroup, Post, SourceFeed


class CommunitiesSmokeTest(TestCase):
    def setUp(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)  # idempotent
        self.oulu = CommunityGroup.objects.get(slug="oulu")
        self.user = User.objects.create_user(email="m@example.com", password="x")
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_seed(self):
        self.assertEqual(SourceFeed.objects.filter(community=self.oulu).count(), 7)

    def test_posts_members_only(self):
        url = "/api/communities/groups/oulu/posts/"
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post("/api/communities/groups/oulu/join/").status_code, 200)
        r = self.client.post(url, {"body": "Hello Oulu", "kind": "post"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(Post.objects.count(), 1)

    def test_recurring_question(self):
        for body in ["How do I get a tax card?", "how do i get a TAX card", "How do I get a tax card??"]:
            c, _ = services.record_question(community=self.oulu, author=self.user, body=body)
        self.assertEqual(c.occurrence_count, 3)
        self.assertTrue(c.is_story_candidate)

    def test_sources_admin_only(self):
        self.assertEqual(self.client.get("/api/communities/sources/").status_code, 403)
