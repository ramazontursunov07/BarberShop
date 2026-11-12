"""Doimiy bronlar uchun yaqin 2 haftalik uchrashuvlarni avtomatik bron qiladi. Kuniga 1 marta cron:
    python manage.py book_recurring
"""
from django.core.management.base import BaseCommand

from apps.bookings import recurring


class Command(BaseCommand):
    help = "Doimiy bronlarni avtomatik yaratadi"

    def handle(self, *args, **options):
        r = recurring.book_due()
        self.stdout.write(self.style.SUCCESS(f"Bron qilindi: {r['booked']}, band bo'lgani: {r['conflicts']}"))
        