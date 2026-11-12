"""Xizmatdan keyin mijozdan baho so'raydi (Telegram tugmalari 1–5). Har 15–30 daqiqada cron:
    python manage.py send_review_requests            # tugagandan 2 soat o'tgach
    python manage.py send_review_requests --hours 1
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from apps.ai.models import Notification
from apps.ai import notify
from apps.bookings.models import Booking
from apps.bookings.services import master_name


def keyboard(booking_id: int) -> dict:
    return {"inline_keyboard": [[{"text": "⭐" * n, "callback_data": f"rate:{booking_id}:{n}"} for n in (1, 2, 3, 4, 5)]]}


class Command(BaseCommand):
    help = "Bajarilgan bronlar uchun baho so'rovi yuboradi"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=2)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        now = timezone.now()
        qs = (Booking.objects.filter(status=Booking.Status.COMPLETED, review__isnull=True,
                                     end_time__lte=now - timedelta(hours=options["hours"]),
                                     end_time__gte=now - timedelta(hours=48),
                                     client__telegram_id__isnull=False)
              .exclude(notifications__kind=Notification.Kind.REVIEW_REQUEST)
              .select_related("client", "master__user", "master__shop", "service"))
        sent = failed = 0
        for b in qs:
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] #{b.id}")
                continue
            try:
                note = Notification.objects.create(user=b.client, booking=b, kind=Notification.Kind.REVIEW_REQUEST)
            except IntegrityError:
                continue
            text = (f"Xizmatimizdan mamnunmisiz? {b.master.shop.name}, usta {master_name(b.master)} "
                    f"(«{b.service.name}»). Iltimos, baho bering:")
            if notify.send_telegram(b.client.telegram_id, text, reply_markup=keyboard(b.id)):
                sent += 1
            else:
                note.delete()
                failed += 1
        self.stdout.write(self.style.SUCCESS(f"Yuborildi: {sent}, xato: {failed}"))
