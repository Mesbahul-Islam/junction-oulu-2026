from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from apps.communities.models import CommunityGroup
from apps.feed.models import SourceDocument

from .models import DESKS, AgentRun
from .newsroom import copy_desk, desks, runner
from .serializers import AgentRunDetailSerializer


SOURCE = {"title": "Kirjasto avautuu", "body": "Kirjasto avautuu maanantaina.",
          "url": "https://example.com/news", "publisher": "Kaleva"}
ANSWER = {"headline": SOURCE["title"], "summary": SOURCE["body"], "key_facts": [],
          **{k: "Lähteen tiedot eivät riitä vaikutusten arviointiin." for k in desks.SITUATIONS}}


class ExplainerTests(SimpleTestCase):
    @patch.object(desks.ai, "ask_json", return_value=(ANSWER, ""))
    def test_one_call_uses_original_source_and_allows_no_extra_facts(self, ask):
        result = desks.explainer({"source": SOURCE})
        ask.assert_called_once()
        agent, prompt, keys = ask.call_args.args
        self.assertEqual(agent, "explainer")
        self.assertIn(SOURCE["title"], prompt)
        self.assertIn(SOURCE["body"], prompt)
        self.assertEqual(set(keys), set(ANSWER))
        self.assertEqual(result["draft"]["key_facts"], [])
        self.assertEqual(result["explainer"]["newcomer"], ANSWER["newcomer"])
        self.assertEqual(result["issues"], [])

    def test_failure_or_malformed_output_preserves_source_and_blocks(self):
        invalid = [None, {**ANSWER, "summary": " "}, {**ANSWER, "headline": None},
                   {**ANSWER, "key_facts": "invented"}, {**ANSWER, "key_facts": [None]},
                   {**ANSWER, "student": {"unexpected": "object"}}]
        for answer in invalid:
            with self.subTest(answer=answer), patch.object(desks.ai, "ask_json", return_value=(answer, "")):
                result = desks.explainer({"source": SOURCE})
                self.assertEqual(result["draft"], {"headline": SOURCE["title"], "summary": SOURCE["body"],
                                                  "key_facts": []})
                self.assertEqual(result["explainer"], {})
                self.assertEqual(copy_desk.verdict(result["issues"]), "needs_review")

    @patch.object(desks.ai, "ask_json", return_value=(None, "offline"))
    def test_title_only_source_survives_model_failure(self, ask):
        result = desks.explainer({"source": {**SOURCE, "body": ""}})
        self.assertEqual(result["draft"]["summary"], SOURCE["title"])
        self.assertTrue(result["issues"][0]["blocking"])


class NewsroomPipelineTests(TestCase):
    def test_shift_skips_reporter_and_files_combined_output_for_review(self):
        community = CommunityGroup.objects.create(name="Oulu", slug="oulu", languages=["fi"])
        doc = SourceDocument.objects.create(**SOURCE, content_hash="test-source")
        run = AgentRun.objects.create(community=community, max_stories=1)
        pick = {"doc": doc, "score": 0.8, "ranked_by": "heuristic", "reasons": [], "jev": 0.8, "votes": 0}
        with patch.object(runner.wire, "run_wire_desk", return_value={"candidates": [doc], "report": {}}), \
             patch.object(runner.news_editor, "rank", return_value=[pick]), \
             patch.object(desks.ai, "ask_json", return_value=(ANSWER, "")) as ask:
            runner.run_newsroom(run)
        self.assertEqual(run.status, AgentRun.Status.SUCCEEDED)
        ask.assert_called_once()
        story = run.stories.get()
        self.assertEqual(story.stage, "done")
        self.assertEqual(list(run.steps.values_list("agent", flat=True)),
                         ["wire", "news_editor", "explainer", "translator", "fact_checker", "standards",
                          "copy_desk", "community_vote"])
        version = story.snippet.versions.get(language="fi")
        self.assertEqual(version.summary, SOURCE["body"])
        self.assertEqual(version.explainer["student"], ANSWER["student"])
        self.assertEqual(story.snippet.review_status, "pending_review")
        self.assertIsNone(story.snippet.published_at)
        self.assertTrue(story.snippet.review_tasks.filter(status="open").exists())
        dashboard = AgentRunDetailSerializer(run).data
        self.assertNotIn("reporter", [d["key"] for d in dashboard["desks"]])
        self.assertNotIn("reporter", dict(DESKS))


    def test_empty_shift_marks_unused_story_desks_skipped(self):
        community = CommunityGroup.objects.create(name="Oulu", slug="oulu", languages=["fi"])
        run = AgentRun.objects.create(community=community, max_stories=4)
        report = {"fetched": 25, "new": 0, "candidates": 0, "errors": []}
        with patch.object(runner.wire, "run_wire_desk", return_value={"candidates": [], "report": report}), \
             patch.object(runner.news_editor, "rank", return_value=[]), \
             patch.object(desks.ai, "ask_json") as ask:
            runner.run_newsroom(run)
        ask.assert_not_called()
        self.assertEqual(run.status, "succeeded")
        data = AgentRunDetailSerializer(run).data
        states = {desk["key"]: desk["status"] for desk in data["desks"]}
        self.assertEqual(states["wire"], "done")
        self.assertEqual(states["news_editor"], "done")
        for key in ("explainer", "translator", "fact_checker", "standards", "copy_desk"):
            self.assertEqual(states[key], "skipped")


class DashboardSettingsTests(TestCase):
    def request_dashboard(self, staff=True):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import DashboardView

        request = APIRequestFactory().get('/api/agents/dashboard/')
        force_authenticate(request, user=get_user_model()(email="staff@example.com", is_staff=staff, is_superuser=staff))
        return DashboardView.as_view()(request)

    def test_reports_actual_scheduler_interval_and_hides_secrets(self):
        from datetime import timedelta
        import json
        from django.test import override_settings
        from django.utils import timezone
        from django_celery_beat.models import IntervalSchedule, PeriodicTask

        last = timezone.now()
        interval = IntervalSchedule.objects.create(every=7200, period='seconds')
        PeriodicTask.objects.create(name='test-newsroom', task='apps.agents.tasks.ingest_all_communities',
                                    interval=interval, last_run_at=last, enabled=True)
        with override_settings(AGENT_SCHEDULE_MINUTES=30, LLM_MODEL='stub', LLM_AGENT_MODELS={},
                               LLM_API_KEY='private-shared-key', LLM_API_KEYS={'groq': 'private-groq-key'},
                               TYPESAFE_API_KEY='private-jev-key'):
            response = self.request_dashboard()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['schedule']['every_minutes'], 120)
        self.assertEqual(response.data['schedule']['next_run_at'], last + timedelta(hours=2))
        self.assertTrue(response.data['settings']['credentials']['groq'])
        self.assertTrue(response.data['settings']['ranking']['jev_configured'])
        serialized = json.dumps(response.data, default=str)
        for secret in ('private-shared-key', 'private-groq-key', 'private-jev-key'):
            self.assertNotIn(secret, serialized)

    @patch('apps.agents.views.DashboardView._llm_status', return_value=[])
    def test_paused_schedule_has_no_next_dispatch(self, models):
        from django_celery_beat.models import IntervalSchedule, PeriodicTask
        from django.utils import timezone

        interval = IntervalSchedule.objects.create(every=2, period='hours')
        PeriodicTask.objects.create(name='paused-newsroom', task='apps.agents.tasks.ingest_all_communities',
                                    interval=interval, enabled=False, last_run_at=timezone.now())
        response = self.request_dashboard()
        self.assertFalse(response.data['schedule']['enabled'])
        self.assertIsNone(response.data['schedule']['next_run_at'])

    def test_settings_remain_staff_only(self):
        self.assertEqual(self.request_dashboard(staff=False).status_code, 403)

    @patch('apps.agents.views.DashboardView._llm_status', return_value=[])
    def test_counts_follow_decisions_and_keep_real_translation_work(self, models):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIRequestFactory, force_authenticate
        from apps.editorial import services
        from apps.editorial.models import ChecklistItem, ReviewTask
        from apps.editorial.views import ReviewTaskViewSet
        from apps.feed.models import Snippet, SnippetVersion

        user = get_user_model().objects.create_user(email='badge-editor@example.com', is_staff=True, is_superuser=True)
        tasks = []
        for _ in range(2):
            snippet = Snippet.objects.create(review_status='pending_review', confidence=1.0)
            for language in ('fi', 'en'):
                SnippetVersion.objects.create(snippet=snippet, language=language, headline='News', summary='Source text')
            editor = ReviewTask.objects.create(snippet=snippet, required_role='editor')
            ReviewTask.objects.create(snippet=snippet, required_role='language_reviewer', language='en')
            tasks.append(editor)
        ChecklistItem.objects.create(snippet=tasks[1].snippet, key='privacy', label='Check privacy')
        before = self.request_dashboard().data['counts']
        self.assertEqual((before['editor_tasks'], before['translation_tasks']), (2, 2))
        services.approve(tasks[0], user)
        services.reject(tasks[1], user, 'Insufficient evidence')
        counts = self.request_dashboard().data['counts']
        self.assertEqual((counts['editor_tasks'], counts['translation_tasks'], counts['checklist_pending']), (0, 1, 0))
        request = APIRequestFactory().get('/api/editorial/tasks/')
        force_authenticate(request, user=user)
        queue = ReviewTaskViewSet.as_view({'get': 'list'})(request)
        self.assertEqual(queue.data['count'], counts['editor_tasks'] + counts['translation_tasks'])
        self.assertEqual(queue.data['results'][0]['language'], 'en')
        self.assertEqual(queue.data['results'][0]['snippet'], tasks[0].snippet_id)
        # Rejection history is retained; only its obsolete open work is hidden.
        self.assertTrue(services.queue_for(user).filter(pk=tasks[1].pk, status='rejected').exists())

    @patch('apps.agents.views.DashboardView._llm_status', return_value=[])
    def test_counts_match_the_signed_in_reviewers_permissions(self, models):
        from django.contrib.auth import get_user_model
        from apps.accounts.models import UserRole
        from apps.editorial.models import ReviewTask
        from apps.feed.models import Snippet
        from rest_framework.test import APIRequestFactory, force_authenticate
        from .views import DashboardView

        user = get_user_model().objects.create_user(email='uk-reviewer@example.com', is_staff=True)
        UserRole.objects.create(user=user, role='language_reviewer', language='uk')
        snippet = Snippet.objects.create(review_status='pending_review')
        ReviewTask.objects.create(snippet=snippet, required_role='editor')
        for language in ('uk', 'ar'):
            ReviewTask.objects.create(snippet=snippet, required_role='language_reviewer', language=language)
        request = APIRequestFactory().get('/api/agents/dashboard/')
        force_authenticate(request, user=user)
        counts = DashboardView.as_view()(request).data['counts']
        self.assertEqual((counts['editor_tasks'], counts['translation_tasks']), (0, 1))
