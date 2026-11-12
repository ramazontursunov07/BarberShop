"""Usta kasal/dam olish kunini belgilaydi: shu kundagi bronlar bekor qilinib, mijozlarga Telegram xabar ketadi."""
from datetime import date as date_cls, datetime, time

from django.db import IntegrityError, transaction

from .models import DayOff, Master


class DayOffError(ValueError):
    pass


def can_manage(actor, master: Master) -> bool:
    return actor.id == master.user_id or actor.id == master.shop.owner_id


def mark_day_off(actor, master: Master, day: date_cls, reason: str = "") -> dict:
    """DayOff yaratadi, shu kundagi faol bronlarni bekor qiladi va mijozlarga xabar yuboradi."""
    from apps.ai.models import Notification
    from apps.bookings import events
    from apps.bookings.models import Booking
    from apps.bookings.services import ACTIVE_STATUSES, SHOP_TZ

    if not can_manage(actor, master):
        raise PermissionError("Bu ustaning jadvalini o'zgartirishga ruxsat yo'q")
    if day < datetime.now(SHOP_TZ).date():
        raise DayOffError("O'tgan kunni dam olish kuni qilib bo'lmaydi")

    with transaction.atomic():
        try:
            with transaction.atomic():
                DayOff.objects.create(master=master, date=day, reason=reason[:100])
        except IntegrityError:
            raise DayOffError("Bu kun allaqachon dam olish kuni qilib belgilangan")
        start = datetime.combine(day, time.min, tzinfo=SHOP_TZ)
        end = datetime.combine(day, time.max, tzinfo=SHOP_TZ)
        bookings = list(
            Booking.objects.select_for_update()
            .filter(master=master, status__in=ACTIVE_STATUSES, start_time__gte=start, start_time__lte=end)
            .select_related("client", "master__user", "master__shop", "service")
            .prefetch_related("extra_services")
        )
        for b in bookings:
            b.status = Booking.Status.CANCELLED
            b.save(update_fields=["status"])
            Notification.objects.get_or_create(user=b.client, booking=b, kind=Notification.Kind.DAY_OFF)
            events.notify_client_day_off(b, reason)
    return {"date": day.isoformat(), "reason": reason, "cancelled_bookings": len(bookings)}


def remove_day_off(actor, master: Master, day: date_cls) -> bool:
    if not can_manage(actor, master):
        raise PermissionError("Bu ustaning jadvalini o'zgartirishga ruxsat yo'q")
    deleted, _ = DayOff.objects.filter(master=master, date=day).delete()
    return bool(deleted)
