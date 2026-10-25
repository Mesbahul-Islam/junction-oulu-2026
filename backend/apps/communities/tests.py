from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase

from . import photos
from .models import CommunityGroup, PhotoBlob, Post


class PostPhotoTests(TestCase):
    """Photos are stored in the database and open only through a signed, expiring link."""

    def setUp(self):
        community = CommunityGroup.objects.create(name="Oulu", slug="oulu")
        author = get_user_model().objects.create_user(username="a", email="a@example.com", password="x")
        self.post = Post.objects.create(community=community, author=author, body="hi", image_status="pending")
        self.post.image.save("p.jpg", ContentFile(b"jpeg"), save=True)

    def test_stored_in_the_database(self):
        self.assertEqual(bytes(PhotoBlob.objects.get(name=self.post.image.name).data), b"jpeg")
        self.post.image.delete(save=False)
        self.assertFalse(PhotoBlob.objects.exists())

    def test_signed_link_serves_the_photo(self):
        token = photos._signer.sign(str(self.post.pk))
        res = self.client.get(f"/api/communities/photo/{token}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(b"".join(res.streaming_content), b"jpeg")

    def test_forged_or_expired_link_is_refused(self):
        self.assertEqual(self.client.get(f"/api/communities/photo/{self.post.pk}/").status_code, 404)
        token = photos._signer.sign(str(self.post.pk))
        with patch.object(photos, "LINK_MAX_AGE", -1):
            self.assertEqual(self.client.get(f"/api/communities/photo/{token}/").status_code, 404)
