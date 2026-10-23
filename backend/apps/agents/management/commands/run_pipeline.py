"""Run the LangGraph newsroom once, synchronously, for one community.

    python manage.py run_pipeline oulu --max-items 3

Results land in the editorial review queue (never published automatically).
"""

from django.core.management.base import BaseCommand, CommandError

from apps.agents.models import AgentRun
from apps.agents.tasks import ingest_and_run
from apps.communities.models import CommunityGroup


class Command(BaseCommand):
    help = "Fetch the community's sources and run all agents once (no Celery needed)."

    def add_arguments(self, parser):
        parser.add_argument("community", help="Community slug, e.g. oulu")
        parser.add_argument("--max-items", type=int, default=3, help="Stories to process (default 3)")

    def handle(self, *args, community, max_items, **options):
        try:
            group = CommunityGroup.objects.get(slug=community)
        except CommunityGroup.DoesNotExist:
            raise CommandError(f"No community with slug {community!r}. Did you run bootstrap?")
        result = ingest_and_run(group.id, trigger=AgentRun.Trigger.MANUAL, max_items=max_items)
        self.stdout.write(self.style.SUCCESS(
            f"Run {result['run_id']}: {len(result['snippets'])} snippet(s) sent to the review queue "
            f"-> /admin/agents/agentrun/{result['run_id']}/"
        ))
