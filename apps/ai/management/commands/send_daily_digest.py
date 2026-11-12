"""Har ertalab ustalarga bugungi jadval, egasiga umumiy xulosa yuboradi (Telegram). Kuniga 1 marta cron:
    python manage.py send_daily_digest
"""
from datetime import datetime, time

from django.core.management.base import BaseCommand

from apps.ai import notify
from apps.bookings.models import Booking
from apps.bookings.services import ACTIVE_STATUSES, SHOP_TZ, services_label
from apps.masters.models import Master
from apps.shops.models import Shop


def _day_bounds():
    today = datetime.now(SHOP_TZ).date()
    return today, datetime.combine(today, time.min, tzinfo=SHOP_TZ), datetime.combine(today, time.max, tzinfo=SHOP_TZ)


def master_digest(master: Master) -> str | None:
    today, a, b = _day_bounds()
    rows = (Booking.objects.filter(master=master, status__in=ACTIVE_STATUSES, start_time__range=(a, b))
            .select_related("client", "service").prefetch_related("extra_services").order_by("start_time"))
    if not rows:
        return None
    lines = [f"📅 Bugungi jadval ({today:%d.%m}):"]
    for r in rows:
        lines.append(f"{r.start_time.astimezone(SHOP_TZ):%H:%M} — {r.client.first_name} ({r.client.phone}), {services_label(r)}")
    return "\n".join(lines)


def owner_digest(shop: Shop) -> str | None:
    today, a, b = _day_bounds()
    rows = list(Booking.objects.filter(master__shop=shop, status__in=ACTIVE_STATUSES, start_time__range=(a, b)))
    if not rows:
        return None
    total = sum(int(r.price) for r in rows)
    return f"📊 {shop.name}: bugun {len(rows)} ta bron, kutilayotgan tushum {total:,} so'm.".replace(",", " ")


class Command(BaseCommand):
    help = "Ustalar va egalariga kunlik xulosa"

    def handle(self, *args, **options):
        sent = 0
        for m in Master.objects.filter(is_active=True, user__telegram_id__isnull=False).select_related("user"):
            text = master_digest(m)
            if text and notify.send_telegram(m.user.telegram_id, text):
                sent += 1
        for s in Shop.objects.filter(is_active=True, owner__telegram_id__isnull=False).select_related("owner"):
            text = owner_digest(s)
            if text and notify.send_telegram(s.owner.telegram_id, text):
                sent += 1
        self.stdout.write(self.style.SUCCESS(f"Yuborildi: {sent}"))
        