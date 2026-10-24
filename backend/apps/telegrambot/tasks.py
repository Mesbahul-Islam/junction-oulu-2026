from celery import shared_task
from django.conf import settings


@shared_task
def send_morning_news():
    """Daily digest for Telegram readers (schedule in config/celery.py)."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return {"skipped": "no TELEGRAM_API token"}
    from .digest import send_all

    return send_all()
