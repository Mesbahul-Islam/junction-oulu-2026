import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

app.conf.beat_schedule = {
    "ingest-all-communities": {
        "task": "apps.agents.tasks.ingest_all_communities",
        "schedule": crontab(minute="*/30"),
    },
    "expire-snippets": {
        "task": "apps.agents.tasks.expire_snippets",
        "schedule": crontab(minute="*/15"),
    },
    "settle-finished-events": {
        "task": "apps.markets.tasks.settle_finished_events",
        "schedule": crontab(minute="*/5"),
    },
}
