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
    # Prediction markets (apps.markets.tasks.settle_finished_events) are off: no screen uses them.
    "telegram-morning-news": {
        "task": "apps.telegrambot.tasks.send_morning_news",
        "schedule": crontab(hour=8, minute=0),  # Helsinki time (CELERY_TIMEZONE)
    },
    # Lämäri (apps.fantasy.tasks) runs nothing in the background: sync_schedule, sync_live and
    # sports_desk are off. Run them by hand if needed, e.g. manage.py sync_liiga.
}
