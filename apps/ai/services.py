"""ORM qatlami: AI agent chaqiradigan funksiyalar.

Sizning modellaringizga moslangan:
  Shop(name, city, district, address, phone, opens_at, closes_at, is_active)
  Master(user -> first_name/last_name, shop, is_active)
  WorkSchedule(master, weekday 0=Dushanba, start_time, end_time)
  DayOff(master, date)
  Service(shop, name, price, duration_minutes, is_active)
  Booking(client, master, service, start_time, end_time: DateTime, price, status)
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone

from apps.bookings.models import Booking
from apps.masters.models import DayOff, Master, WorkSchedule
from apps.services.models import Service
from apps.shops.models import Shop

from .slots import compute_slots

# Sartaroshxona ish vaqtlari shu vaqt mintaqasida deb hisoblanadi
SHOP_TZ = ZoneInfo("Asia/Tashkent")
SLOT_STEP_MINUTES = 30
# Band hisoblanmaydigan bron holatlari
FREE_STATUSES = [Booking.Status.CANCELLED, Booking.Status.NO_SHOW]


def _master_name(master: Master) -> str:
    # Telefon raqamni modelga bermaymiz: faqat ism
    user = master.user
    return f"{user.first_name} {user.last_name}".strip() or f"Usta #{master.id}"


def _parse_date(value: str):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ValueError("Sana 'YYYY-MM-DD' formatida bo'lishi kerak")


def _parse_time(value: str):
    try:
        return datetime.strptime(value, "%H:%M").time()
    except (TypeError, ValueError):
        raise ValueError("Vaqt 'HH:MM' formatida bo'lishi kerak")


def _local_now() -> datetime:
    return timezone.now().astimezone(SHOP_TZ)


# ------------------------------------------------------------------ o'qish

def list_shops(user, city: str | None = None) -> list[dict]:
    qs = Shop.objects.filter(is_active=True)
    if city:
        qs = qs.filter(city__icontains=city)
    return [
        {
            "id": s.id,
            "name": s.name,
            "city": s.city,
            "district": s.district,
            "address": s.address,
            "opens_at": s.opens_at.strftime("%H:%M"),
            "closes_at": s.closes_at.strftime("%H:%M"),
            "description": s.description[:300],
        }
        for s in qs[:30]
    ]


def list_services(user, shop_id: int | None = None) -> list[dict]:
    qs = Service.objects.filter(is_active=True, shop__is_active=True).select_related("shop")
    if shop_id:
        qs = qs.filter(shop_id=shop_id)
    return [
        {
            "id": s.id,
            "shop_id": s.shop_id,
            "shop": s.shop.name,
            "name": s.name,
            "price": int(s.price),
            "duration_minutes": s.duration_minutes,
        }
        for s in qs[:50]
    ]


def list_masters(user, shop_id: int | None = None) -> list[dict]:
    qs = Master.objects.filter(is_active=True, shop__is_active=True).select_related("user", "shop")
    if shop_id:
        qs = qs.filter(shop_id=shop_id)
    return [
        {
            "id": m.id,
            "shop_id": m.shop_id,
            "shop": m.shop.name,
            "name": _master_name(m),
            "bio": m.bio[:200],
        }
        for m in qs[:50]
    ]


def _get_slots(master: Master, service: Service, day) -> list[str]:
    if master.shop_id != service.shop_id:
        raise ValueError("Bu xizmat tanlangan ustaning sartaroshxonasiga tegishli emas")

    if DayOff.objects.filter(master=master, date=day).exists():
        return []

    schedule = WorkSchedule.objects.filter(master=master, weekday=day.weekday()).first()
    if schedule is None:
        return []  # usta bu kuni ishlamaydi

    shop = master.shop
    work_start = max(schedule.start_time, shop.opens_at)
    work_end = min(schedule.end_time, shop.closes_at)
    if work_start >= work_end:
        return []

    day_start = datetime.combine(day, datetime.min.time(), tzinfo=SHOP_TZ)
    day_end = day_start + timedelta(days=1)
    bookings = (
        Booking.objects.filter(master=master, start_time__gte=day_start, start_time__lt=day_end)
        .exclude(status__in=FREE_STATUSES)
    )
    busy = [
        (b.start_time.astimezone(SHOP_TZ).time(), b.end_time.astimezone(SHOP_TZ).time())
        for b in bookings
    ]

    return compute_slots(
        day=day,
        work_start=work_start,
        work_end=work_end,
        busy=busy,
        duration_minutes=service.duration_minutes,
        step_minutes=SLOT_STEP_MINUTES,
        now=_local_now().replace(tzinfo=None),
    )


def get_available_slots(user, master_id: int, service_id: int, date: str) -> dict:
    day = _parse_date(date)
    master = Master.objects.select_related("user", "shop").get(pk=master_id, is_active=True)
    service = Service.objects.get(pk=service_id, is_active=True)
    return {
        "master": _master_name(master),
        "service": service.name,
        "date": date,
        "slots": _get_slots(master, service, day),
    }


# ------------------------------------------------------------------ yozish

def create_booking(user, master_id: int, service_id: int, date: str, start_time: str) -> dict:
    """Bron yaratadi. Mijoz HAR DOIM so'rov yuborgan foydalanuvchi (model emas!)."""
    if user.blocked_until and user.blocked_until > timezone.now():
        return {"error": "Sizning hisobingiz vaqtincha bloklangan, bron qilib bo'lmaydi."}

    day = _parse_date(date)
    start = _parse_time(start_time)

    with transaction.atomic():
        # Ikkita bir vaqtdagi so'rov bir slotni olmasligi uchun ustani qulflaymiz
        master = Master.objects.select_for_update().get(pk=master_id, is_active=True)
        master = Master.objects.select_related("user", "shop").get(pk=master.pk)
        service = Service.objects.get(pk=service_id, is_active=True)

        if start_time not in _get_slots(master, service, day):
            return {"error": "Bu vaqt band yoki ish vaqtidan tashqarida. Boshqa vaqt tanlang."}

        start_dt = datetime.combine(day, start, tzinfo=SHOP_TZ)
        end_dt = start_dt + timedelta(minutes=service.duration_minutes)
        booking = Booking.objects.create(
            client=user,
            master=master,
            service=service,
            start_time=start_dt,
            end_time=end_dt,
            price=service.price,
            status=Booking.Status.PENDING,
        )

    return {
        "booking_id": booking.id,
        "shop": master.shop.name,
        "master": _master_name(master),
        "service": service.name,
        "price": int(service.price),
        "date": date,
        "start_time": start_time,
        "end_time": end_dt.strftime("%H:%M"),
        "status": "pending",
    }
