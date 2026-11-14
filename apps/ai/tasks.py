"""Davriy vazifalar: management command'larni Celery orqali chaqiradi (jadval: config/celery.py)."""
from celery import shared_task
from django.core.management import call_command


@shared_task(name="apps.ai.tasks.send_reminders")
def send_reminders():
    call_command("send_reminders")


@shared_task(name="apps.ai.tasks.send_review_requests")
def send_review_requests():
    call_command("send_review_requests")


@shared_task(name="apps.ai.tasks.book_recurring")
def book_recurring():
    call_command("book_recurring")


@shared_task(name="apps.ai.tasks.send_daily_digest")
def send_daily_digest():
    call_command("send_daily_digest")


@shared_task(name="apps.ai.tasks.backup_db")
def backup_db():
    call_command("backup_db")


@shared_task(name="apps.ai.tasks.winback")
def winback():
    call_command("winback")
