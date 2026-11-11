"""Egasi uchun statistika: daromad, eng ko'p so'ralgan xizmat, band soatlar, ustalar kesimi."""
from collections import Counter, defaultdict
from datetime import timedelta

from django.utils import timezone

from apps.bookings.models import Booking
from apps.bookings.services import SHOP_TZ, master_name

WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
MAX_DAYS = 365


def shop_stats(shop, days: int = 30, now=None) -> dict:
    """Oxirgi `days` kun ichidagi (start_time bo'yicha) bronlar statistikasi.

    - daromad faqat BAJARILGAN bronlar narxidan (chegirmadan keyingi yakuniy summa);
    - xizmat, soat va kun bo'yicha talab bekor qilinmagan bronlardan hisoblanadi.
    """
    now = now or timezone.now()
    days = max(1, min(days, MAX_DAYS))
    since = now - timedelta(days=days)

    rows = list(
        Booking.objects.filter(master__shop=shop, start_time__gte=since, start_time__lte=now)
        .select_related("master__user", "service")
    )

    by_status = Counter(b.status for b in rows)
    completed = [b for b in rows if b.status == Booking.Status.COMPLETED]
    demand = [b for b in rows if b.status != Booking.Status.CANCELLED]

    revenue = sum(int(b.price) for b in completed)

    services = defaultdict(lambda: {"bookings": 0, "revenue": 0})
    for b in demand:
        services[b.service.name]["bookings"] += 1
    for b in completed:
        services[b.service.name]["revenue"] += int(b.price)
    top_services = sorted(
        ({"service": name, **vals} for name, vals in services.items()),
        key=lambda x: (-x["bookings"], -x["revenue"], x["service"]),
    )

    hours = Counter(b.start_time.astimezone(SHOP_TZ).hour for b in demand)
    weekdays = Counter(b.start_time.astimezone(SHOP_TZ).weekday() for b in demand)

    masters = {}
    for b in demand:
        m = masters.setdefault(b.master_id, {"master": master_name(b.master), "bookings": 0, "completed": 0,
                                              "revenue": 0})
        m["bookings"] += 1
        if b.status == Booking.Status.COMPLETED:
            m["completed"] += 1
            m["revenue"] += int(b.price)

    total = len(rows)
    no_show = by_status.get(Booking.Status.NO_SHOW, 0)
    cancelled = by_status.get(Booking.Status.CANCELLED, 0)

    return {
        "period_days": days,
        "total_bookings": total,
        "by_status": {s.value: by_status.get(s.value, 0) for s in Booking.Status},
        "completed": len(completed),
        "revenue": revenue,
        "average_check": round(revenue / len(completed)) if completed else 0,
        "cancel_rate": round(cancelled / total, 3) if total else 0,
        "no_show_rate": round(no_show / total, 3) if total else 0,
        "top_services": top_services,
        "busiest_hours": [
            {"hour": f"{h:02d}:00", "bookings": n} for h, n in sorted(hours.items(), key=lambda x: (-x[1], x[0]))
        ],
        "busiest_weekdays": [
            {"weekday": WEEKDAYS[d], "bookings": n} for d, n in sorted(weekdays.items(), key=lambda x: (-x[1], x[0]))
        ],
        "masters": sorted(masters.values(), key=lambda x: (-x["revenue"], -x["bookings"])),
    }
