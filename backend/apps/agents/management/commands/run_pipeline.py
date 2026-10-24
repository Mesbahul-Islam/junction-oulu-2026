"""Run one AI newsroom shift synchronously (no Celery needed).

    python manage.py run_pipeline --stories 3

Fetches the Kaleva feeds, lets Jev pick the stories and sends each through the desks.
Results land in the review queue as Ready to send or Needs review (never published).
"""

from django.core.management.base import BaseCommand

from apps.agents import services
from apps.agents.models import AgentRun
from apps.agents.newsroom.runner import run_newsroom


class Command(BaseCommand):
    help = "Run one AI newsroom shift now."

    def add_arguments(self, parser):
        parser.add_argument("--stories", type=int, default=None, help="Stories to cover (default AGENT_MAX_ITEMS)")

    def handle(self, *args, stories, **options):
        run = run_newsroom(services.create_run(AgentRun.Trigger.MANUAL, stories))
        result = run.state.get("result") or {}
        self.stdout.write(self.style.SUCCESS(
            f"Run {run.pk} {run.status}: {result.get('ready', 0)} ready to send, "
            f"{result.get('needs_review', 0)} need review, {result.get('failed', 0)} failed. {run.error}"
        ))
