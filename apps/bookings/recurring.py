"""Doimiy bron: "har 3 haftada shu usta, shu soat". Cron har kuni keyingi uchrashuvlarni avtomatik bron qiladi."""
from datetime import date, datetime, time, timedelta

from apps.masters.models import Master
from apps.services.models import Service

from .models import RecurringBooking
from .services import SHOP_TZ, BookingError, master_name

HORIZON_DAYS = 14  # necha kun oldindan avtomatik bron qilinadi


def rule_to_dict(r: RecurringBooking) -> dict:
    return {
        "id": r.id, "master": master_name(r.master), "service": r.service.name,
        "weekday": r.start_date.weekday(), "start_time": f"{r.start_time:%H:%M}",
        "every_weeks": r.every_weeks, "start_date": r.start_date.isoformat(),
        "end_date": r.end_date.isoformat() if r.end_date else None, "is_active": r.is_active,
    }


def create(user, master_id: int, service_id: int, start_date: date, start_time: time, every_weeks: int = 2,
           end_date: date | None = None) -> dict:
    """Qoidani yaratadi va birinchi uchrashuvni darhol bron qiladi (band bo'lsa — xato, qoida yaratilmaydi)."""
    from apps.ai import services as ai

    if not 1 <= every_weeks <= 12:
        raise BookingError("Takrorlash 1 dan 12 haftagacha bo'lishi kerak")
    if end_date and end_date < start_date:
        raise BookingError("Tugash sanasi boshlanishdan oldin bo'lishi mumkin emas")
    master = Master.objects.filter(pk=master_id, is_active=True).first()
    service = Service.objects.filter(pk=service_id, is_active=True).first()
    if not master or not service or master.shop_id != service.shop_id:
        raise BookingError("Usta yoki xizmat topilmadi")
    res = ai.create_booking(user, master_id, service_id, start_date.isoformat(), f"{start_time:%H:%M}")
    if "error" in res:
        raise BookingError(res["error"])
    rule = RecurringBooking.objects.create(
        client=user, master=master, service=service, start_date=start_date, start_time=start_time,
        every_weeks=every_weeks, end_date=end_date, last_booked_date=start_date,
    )
    return rule_to_dict(rule)


def list_mine(user) -> list[dict]:
    return [rule_to_dict(r) for r in
            RecurringBooking.objects.filter(client=user, is_active=True).select_related("master__user", "service")]


def stop(user, rule_id: int) -> dict:
    r = RecurringBooking.objects.filter(client=user, pk=rule_id, is_active=True).first()
    if not r:
        raise BookingError("Doimiy bron topilmadi")
    r.is_active = False
    r.save(update_fields=["is_active"])
    return {"stopped": True, "id": r.id}


def due_dates(rule: RecurringBooking, today: date, horizon: int = HORIZON_DAYS) -> list[date]:
    step = timedelta(weeks=rule.every_weeks)
    d, out = rule.start_date, []
    while d <= today + timedelta(days=horizon):
        if d >= today and (rule.last_booked_date is None or d > rule.last_booked_date) \
                and (rule.end_date is None or d <= rule.end_date):
            out.append(d)
        d += step
    return out


def book_due(today: date | None = None, horizon: int = HORIZON_DAYS) -> dict:
    """Barcha faol qoidalar uchun yaqin uchrashuvlarni bron qiladi. Band bo'lsa mijozga xabar beradi."""
    from apps.ai import services as ai
    from apps.ai.notify import send_telegram

    today = today or datetime.now(SHOP_TZ).date()
    booked = conflicts = 0
    rules = RecurringBooking.objects.filter(is_active=True).select_related("client", "master__user", "service")
    for r in rules:
        if r.end_date and r.end_date < today:
            r.is_active = False
            r.save(update_fields=["is_active"])
            continue
        for d in due_dates(r, today, horizon):
            res = ai.create_booking(r.client, r.master_id, r.service_id, d.isoformat(), f"{r.start_time:%H:%M}")
            r.last_booked_date = d  # muvaffaqiyatsiz bo'lsa ham qayta-qayta urinmaymiz
            r.save(update_fields=["last_booked_date"])
            if "error" in res:
                conflicts += 1
                if r.client.telegram_id:
                    send_telegram(r.client.telegram_id,
                                  f"Doimiy broningiz uchun {d:%d.%m} soat {r.start_time:%H:%M} band bo'lib chiqdi "
                                  f"({master_name(r.master)}). Boshqa vaqt tanlash uchun botga yozing, "
                                  f"masalan: «{d:%d.%m} {r.service.name.lower()}».")
            else:
                booked += 1
    return {"booked": booked, "conflicts": conflicts}
