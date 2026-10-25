from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.communities.models import CommunityGroup, Membership, Post
from apps.trust.models import MemberTrust

from .services import standing


class StandingTests(TestCase):
    """Perk levels follow trust: the best community wins, and approved photos score."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="a", email="a@example.com", password="x")
        self.oulu = CommunityGroup.objects.create(name="Oulu", slug="oulu")
        self.students = CommunityGroup.objects.create(name="Students", slug="students")
        for c in (self.oulu, self.students):
            Membership.objects.create(user=self.user, community=c)

    def test_no_activity_is_reader(self):
        self.assertEqual(standing(self.user)["level"], "reader")

    def test_best_community_sets_the_level(self):
        MemberTrust.objects.update_or_create(user=self.user, community=self.oulu, defaults={"score": 20, "level": "contributor"})
        MemberTrust.objects.update_or_create(user=self.user, community=self.students, defaults={"score": 55, "level": "eligible"})
        s = standing(self.user)
        self.assertEqual((s["level"], s["community"], s["points"]), ("local_guide", "Students", 55))
        self.assertEqual(s["next"], {"level": "trusted", "editor": True})

    def test_approved_photo_scores(self):
        post = Post.objects.create(community=self.oulu, author=self.user, body="hi", image_status="pending")
        post.image_status = "approved"
        post.save(update_fields=["image_status"])  # what the moderator's decision saves
        self.assertEqual(MemberTrust.objects.get(user=self.user, community=self.oulu).score, 1)
