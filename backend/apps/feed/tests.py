from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings

from . import audio
from .models import AudioClip, Snippet, SnippetVersion


@override_settings(ELEVENLABS_API_KEY="test-key", ELEVENLABS_VOICE="voice")
class ListenTests(TestCase):
    def setUp(self):
        self.version = SnippetVersion.objects.create(
            snippet=Snippet.objects.create(), language="uk", headline="Заголовок", summary="Коротко.",
            key_facts=["Факти."], explainer={"newcomer": "Для вас."},
        )

    def test_script_reads_only_this_versions_text(self):
        self.assertEqual(audio.script(self.version, "newcomer"), "Заголовок\n\nКоротко.\n\nФакти.\n\nДля вас.")
        self.assertNotIn("Для вас", audio.script(self.version, "student"))  # no text in this language: left out

    def test_sami_is_never_voiced(self):
        self.assertTrue(audio.supported("uk"))
        self.assertEqual(audio.model_for("so"), "eleven_v3")
        self.assertFalse(audio.supported("se"))
        with override_settings(ELEVENLABS_API_KEY=""):
            self.assertFalse(audio.supported("uk"))

    @patch.object(audio.httpx, "post")
    def test_clip_is_made_once_and_remade_after_an_edit(self, post):
        post.return_value = MagicMock(content=b"mp3")
        self.assertEqual(audio.clip_for(self.version), b"mp3")
        self.assertEqual(audio.clip_for(self.version), b"mp3")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["json"]["language_code"], "uk")
        self.assertEqual(post.call_args.kwargs["json"]["model_id"], audio.MODEL)
        self.version.summary = "Виправлено."
        audio.clip_for(self.version)
        self.assertEqual(post.call_count, 2)
        self.assertEqual(AudioClip.objects.count(), 2)


@override_settings(ELEVENLABS_API_KEY="test-key", ELEVENLABS_VOICE="voice")
class ListenEndpointTests(TestCase):
    @patch.object(audio.httpx, "post")
    def test_only_an_approved_version_is_voiced(self, post):
        post.return_value = MagicMock(content=b"mp3")
        snippet = Snippet.objects.create(review_status="published")
        SnippetVersion.objects.create(snippet=snippet, language="en", headline="H", summary="S.", review_status="approved")
        SnippetVersion.objects.create(snippet=snippet, language="uk", headline="З", summary="К.")  # pending review

        res = self.client.get(f"/api/feed/snippets/{snippet.pk}/audio/?lang=uk")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "audio/mpeg")
        self.assertEqual(post.call_args.kwargs["json"]["language_code"], "en")  # the version shown, not the draft

        snippet.versions.filter(language="en").update(language="se")
        self.assertEqual(self.client.get(f"/api/feed/snippets/{snippet.pk}/audio/?lang=se").status_code, 404)
