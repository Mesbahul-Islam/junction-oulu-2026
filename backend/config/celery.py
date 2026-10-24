import os

from celery import Celery
from datetime import timedelta

from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

from django.conf import settings  # noqa: E402  (after config_from_object)

app.conf.beat_schedule = {
    "ingest-all-communities": {
        "task": "apps.agents.tasks.ingest_all_communities",
        "schedule": timedelta(minutes=settings.AGENT_SCHEDULE_MINUTES),
    },
    "expire-snippets": {
        "task": "apps.agents.tasks.expire_snippets",
        "schedule": crontab(minute="*/15"),
    },
    "settle-finished-events": {
        "task": "apps.markets.tasks.settle_finished_events",
        "schedule": crontab(minute="*/5"),
    },
    "fantasy-sync-schedule": {
        "task": "apps.fantasy.tasks.sync_schedule",
        "schedule": crontab(hour=6, minute=0),
    },
    # Lämäri sports desk (apps.fantasy.tasks.sports_desk) is off for now; run it by hand if needed.
    "fantasy-sync-live": {
        "task": "apps.fantasy.tasks.sync_live",
        "schedule": crontab(minute="*/10"),
    },
}
