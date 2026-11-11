"""Yaqinlashayotgan bronlar haqida mijozga Telegram eslatma yuboradi.

Har 10-15 daqiqada cron orqali ishga tushiring:
    python manage.py send_reminders            # 3 soat qolgan bronlar
    python manage.py send_reminders --hours 5
    python manage.py send_reminders --dry-run  # yubormasdan ro'yxatni ko'rsatadi
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils import timezone

from apps.ai.models import Notification
from apps.ai.notify import send_telegram
from apps.bookings.models import Booking
from apps.bookings.services import ACTIVE_STATUSES, CANCEL_BEFORE, SHOP_TZ, master_name
from apps.insights.noshow import build_context, risk_score


def build_reminder(booking: Booking) -> str:
    start = booking.start_time.astimezone(SHOP_TZ)
    cancel_hours = int(CANCEL_BEFORE.total_seconds() // 3600)
    return (
        f"⏰ Eslatma: bugun soat {start:%H:%M} da {booking.master.shop.name}da "
        f"{master_name(booking.master)} ustaga «{booking.service.name}» uchun yozilgansiz.\n\n"
        f"Kela olmasangiz, iltimos, kamida {cancel_hours} soat oldin bekor qiling: "
        f"shunchaki «bronimni bekor qil» deb yozing."
    )


def build_risk_reminder(booking: Booking) -> str:
    start = booking.start_time.astimezone(SHOP_TZ)
    cancel_hours = int(CANCEL_BEFORE.total_seconds() // 3600)
    return (
        f"📅 Bron eslatmasi: {start:%d.%m} soat {start:%H:%M} da {booking.master.shop.name}da "
        f"{master_name(booking.master)} ustaga «{booking.service.name}» uchun yozilgansiz.\n\n"
        f"Kela olmasangiz, iltimos, kamida {cancel_hours} soat oldin bekor qiling: "
        f"shunchaki «bronimni bekor qil» deb yozing, shunda bu vaqtni boshqa mijoz oladi."
    )


class Command(BaseCommand):
    help = "Yaqinlashayotgan bronlar uchun Telegram eslatma yuboradi"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=3, help="Bron boshlanishiga necha soat qolganda (standart 3)")
        parser.add_argument("--risky-hours", type=int, default=24,
                            help="No-show xavfi o'rta/yuqori bronlarga shuncha soat oldin qo'shimcha eslatma (0 = o'chiq)")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        now = timezone.now()
        bookings = (
            Booking.objects.filter(
                status__in=ACTIVE_STATUSES,
                start_time__gt=now,
                start_time__lte=now + timedelta(hours=options["hours"]),
                client__telegram_id__isnull=False,
            )
            .exclude(notifications__kind=Notification.Kind.REMINDER)
            .select_related("client", "master__user", "master__shop", "service")
        )

        sent = failed = 0
        for booking in bookings:
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] #{booking.id} -> {booking.client.telegram_id}")
                continue
            try:
                # Avval belgilaymiz: ikki jarayon bir vaqtda ishlasa ham xabar bir marta ketadi
                note = Notification.objects.create(
                    user=booking.client, booking=booking, kind=Notification.Kind.REMINDER
                )
            except IntegrityError:
                continue
            if send_telegram(booking.client.telegram_id, build_reminder(booking)):
                sent += 1
            else:
                note.delete()  # keyingi ishga tushirishda qayta urinadi
                failed += 1

        if options["risky_hours"] > options["hours"]:
            s, f = self.remind_risky(now, options)
            sent, failed = sent + s, failed + f

        self.stdout.write(self.style.SUCCESS(f"Yuborildi: {sent}, xato: {failed}"))

    def remind_risky(self, now, options):
        """Kelmaslik ehtimoli o'rta/yuqori bronlarga oddiy eslatmadan oldin yana bir eslatma (bron vaqti bo'shab qolmasligi uchun)."""
        bookings = (
            Booking.objects.filter(
                status__in=ACTIVE_STATUSES,
                start_time__gt=now + timedelta(hours=options["hours"]),
                start_time__lte=now + timedelta(hours=options["risky_hours"]),
                client__telegram_id__isnull=False,
            )
            .exclude(notifications__kind=Notification.Kind.RISK_REMINDER)
            .select_related("client", "master__user", "master__shop", "service")
        )
        contexts, sent, failed = {}, 0, 0
        for booking in bookings:
            shop_id = booking.master.shop_id
            if shop_id not in contexts:
                contexts[shop_id] = build_context(shop_id)
            risk = risk_score(booking.client, shop_id, booking.start_time, now=booking.created_at,
                              ctx=contexts[shop_id])
            if risk["level"] == "low":
                continue
            if options["dry_run"]:
                self.stdout.write(f"[dry-run] xavfli #{booking.id} ({risk['level']}, {risk['probability']})")
                continue
            try:
                note = Notification.objects.create(
                    user=booking.client, booking=booking, kind=Notification.Kind.RISK_REMINDER
                )
            except IntegrityError:
                continue
            if send_telegram(booking.client.telegram_id, build_risk_reminder(booking)):
                sent += 1
            else:
                note.delete()
                failed += 1
        return sent, failed
