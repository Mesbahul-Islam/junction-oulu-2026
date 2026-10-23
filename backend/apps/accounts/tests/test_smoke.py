from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Interest, User


class AccountsSmokeTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        Interest.objects.create(slug="housing", name="Housing")

    def test_register_creates_profile_and_onboards(self):
        r = self.client.post(
            "/api/accounts/register/", {"email": "a@example.com", "password": "S3cure-pass-123"}, format="json"
        )
        self.assertEqual(r.status_code, 201, r.content)
        user = User.objects.get(email="a@example.com")
        self.assertTrue(hasattr(user, "profile"))

        self.client.force_authenticate(user)
        r = self.client.post(
            "/api/accounts/onboarding/",
            {"interests": ["housing"], "postal_code": "90100", "reader_situation": "newcomer",
             "preferred_language": "en"},
            format="json",
        )
        self.assertEqual(r.status_code, 200, r.content)
        user.refresh_from_db()
        self.assertTrue(user.onboarded)
        self.assertEqual(list(user.profile.interests.values_list("slug", flat=True)), ["housing"])

        r = self.client.get("/api/accounts/me/")
        self.assertEqual(r.json()["email"], "a@example.com")
