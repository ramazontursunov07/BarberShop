"""Celery: kunlik/davriy vazifalar (cron o'rniga). Ishga tushirish: docker-compose'dagi `worker` va `beat` servislari."""
import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("barbershop")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks(["apps.ai"])

app.conf.beat_schedule = {
    "send-reminders": {"task": "apps.ai.tasks.send_reminders", "schedule": crontab(minute="*/10")},
    "send-review-requests": {"task": "apps.ai.tasks.send_review_requests", "schedule": crontab(minute="*/30")},
    "book-recurring": {"task": "apps.ai.tasks.book_recurring", "schedule": crontab(hour=3, minute=0)},
    "send-daily-digest": {"task": "apps.ai.tasks.send_daily_digest", "schedule": crontab(hour=8, minute=0)},
    "backup-db": {"task": "apps.ai.tasks.backup_db", "schedule": crontab(hour=2, minute=30)},
    "winback": {"task": "apps.ai.tasks.winback", "schedule": crontab(hour=11, minute=0)},
}
