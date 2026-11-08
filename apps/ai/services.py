"""ORM bilan ishlaydigan qatlam.

DIQQAT: bu fayl sizning modellaringiz haqida FARAZ qiladi.
Faqat shu fayl tepasidagi sozlamalarni o'z loyihangizga moslang.

Faraz qilingan tuzilma:
  shops.Shop        : id, name
  services.Service  : id, shop(FK), name, price, duration_minutes
  masters.Master    : id, shop(FK), name (yoki __str__)
  masters.WorkSchedule : master(FK), weekday (0=Dushanba), start_time, end_time
  bookings.Booking  : client(FK User), master(FK), service(FK),
                      date, start_time, end_time, status
"""
from datetime import datetime, time, timedelta

from django.apps import apps
from django.db import transaction
from django.utils import timezone

from .slots import compute_slots

# ---------------- SOZLAMALAR: o'z loyihangizga moslang ----------------
MODELS = {
    "shop": "shops.Shop",
    "service": "services.Service",
    "master": "masters.Master",
    "schedule": "masters.WorkSchedule",
    "booking": "bookings.Booking",
}

SERVICE_DURATION_FIELD = "duration_minutes"  # xizmat davomiyligi (daqiqa)
SERVICE_PRICE_FIELD = "price"
SERVICE_SHOP_FIELD = "shop"
MASTER_SHOP_FIELD = "shop"
MASTER_NAME_FIELD = "name"  # bo'lmasa str(master) ishlatiladi

SCHEDULE_MASTER_FIELD = "master"
SCHEDULE_WEEKDAY_FIELD = "weekday"  # 0=Dushanba ... 6=Yakshanba
SCHEDULE_START_FIELD = "start_time"
SCHEDULE_END_FIELD = "end_time"

BOOKING_CLIENT_FIELD = "client"
BOOKING_DATE_FIELD = "date"
BOOKING_START_FIELD = "start_time"
BOOKING_END_FIELD = "end_time"
BOOKING_STATUS_FIELD = "status"
BOOKING_CANCELLED_STATUS = "cancelled"  # band hisoblanmaydigan holat
BOOKING_NEW_STATUS = "pending"  # yangi bronga beriladigan holat

SLOT_STEP_MINUTES = 30


# ----------------------------------------------------------------------


def _m(key: str):
    return apps.get_model(MODELS[key])


def _master_name(master) -> str:
    return getattr(master, MASTER_NAME_FIELD, None) or str(master)


def list_services(user, shop_id: int | None = None) -> list[dict]:
    qs = _m("service").objects.all()
    if shop_id:
        qs = qs.filter(**{f"{SERVICE_SHOP_FIELD}_id": shop_id})
    return [
        {
            "id": s.id,
            "name": str(getattr(s, "name", s)),
            "price": str(getattr(s, SERVICE_PRICE_FIELD, "")),
            "duration_minutes": getattr(s, SERVICE_DURATION_FIELD),
        }
        for s in qs[:50]
    ]


def list_masters(user, shop_id: int | None = None) -> list[dict]:
    qs = _m("master").objects.all()
    if shop_id:
        qs = qs.filter(**{f"{MASTER_SHOP_FIELD}_id": shop_id})
    return [{"id": m.id, "name": _master_name(m)} for m in qs[:50]]


def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Sana 'YYYY-MM-DD' formatida bo'lishi kerak")


def _parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        raise ValueError("Vaqt 'HH:MM' formatida bo'lishi kerak")


def _get_slots(master, service, day) -> list[str]:
    schedule = _m("schedule").objects.filter(
        **{
            SCHEDULE_MASTER_FIELD: master,
            SCHEDULE_WEEKDAY_FIELD: day.weekday(),
        }
    ).first()
    if schedule is None:
        return []  # usta bu kuni ishlamaydi

    bookings = (
        _m("booking")
        .objects.filter(**{"master": master, BOOKING_DATE_FIELD: day})
        .exclude(**{BOOKING_STATUS_FIELD: BOOKING_CANCELLED_STATUS})
    )
    busy = [
        (getattr(b, BOOKING_START_FIELD), getattr(b, BOOKING_END_FIELD))
        for b in bookings
    ]

    return compute_slots(
        day=day,
        work_start=getattr(schedule, SCHEDULE_START_FIELD),
        work_end=getattr(schedule, SCHEDULE_END_FIELD),
        busy=busy,
        duration_minutes=getattr(service, SERVICE_DURATION_FIELD),
        step_minutes=SLOT_STEP_MINUTES,
        now=datetime.now(),
    )


def get_available_slots(user, master_id: int, service_id: int, date: str) -> dict:
    day = _parse_date(date)
    master = _m("master").objects.get(pk=master_id)
    service = _m("service").objects.get(pk=service_id)
    return {
        "master": _master_name(master),
        "date": date,
        "slots": _get_slots(master, service, day),
    }


def create_booking(user, master_id: int, service_id: int, date: str, start_time: str) -> dict:
    """Bron yaratadi. Mijoz HAR DOIM so'rov yuborgan foydalanuvchi (model emas!)."""
    day = _parse_date(date)
    start = _parse_time(start_time)

    with transaction.atomic():
        # Bir vaqtda ikkita bron tushmasligi uchun ustani qulflaymiz
        master = _m("master").objects.select_for_update().get(pk=master_id)
        service = _m("service").objects.get(pk=service_id)

        if start_time not in _get_slots(master, service, day):
            return {"error": "Bu vaqt band yoki ish vaqtidan tashqarida. Boshqa vaqt tanlang."}

        end_dt = datetime.combine(day, start) + timedelta(
            minutes=getattr(service, SERVICE_DURATION_FIELD)
        )
        booking = _m("booking").objects.create(
            **{
                BOOKING_CLIENT_FIELD: user,
                "master": master,
                "service": service,
                BOOKING_DATE_FIELD: day,
                BOOKING_START_FIELD: start,
                BOOKING_END_FIELD: end_dt.time(),
                BOOKING_STATUS_FIELD: BOOKING_NEW_STATUS,
            }
        )

    return {
        "booking_id": booking.id,
        "master": _master_name(master),
        "service": str(getattr(service, "name", service)),
        "date": date,
        "start_time": start_time,
        "end_time": end_dt.strftime("%H:%M"),
    }
