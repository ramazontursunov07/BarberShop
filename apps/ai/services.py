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

from apps.bookings.models import Booking, WaitlistEntry
from apps.masters.models import DayOff, Master, WorkSchedule
from apps.services.models import Service
from apps.shops.models import Shop

from apps.bookings import events as booking_events
from apps.bookings import services as booking_services

from apps.insights import pricing
from apps.promotions import services as promotions
from apps.insights.profile import client_profile

from .slots import PARTS_OF_DAY, compute_slots, rank_slots

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


def _get_slots(master: Master, service: Service, day, exclude_booking_id: int | None = None,
               duration_minutes: int | None = None) -> list[str]:
    """exclude_booking_id: shu bronni band hisoblamaydi (bronni ko'chirishda o'z vaqti bilan to'qnashmasligi uchun)."""
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
    if exclude_booking_id:
        bookings = bookings.exclude(pk=exclude_booking_id)
    busy = [
        (b.start_time.astimezone(SHOP_TZ).time(), b.end_time.astimezone(SHOP_TZ).time())
        for b in bookings
    ]

    return compute_slots(
        day=day,
        work_start=work_start,
        work_end=work_end,
        busy=busy,
        duration_minutes=duration_minutes or service.duration_minutes,
        step_minutes=SLOT_STEP_MINUTES,
        now=_local_now().replace(tzinfo=None),
    )


MAX_EXTRA_SERVICES = 3


def _resolve_extras(service: Service, extra_service_ids) -> list[Service]:
    """Bir tashrifdagi qo'shimcha xizmatlar: o'sha sartaroshxona, faol, takrorsiz, asosiy xizmatdan boshqa."""
    ids = []
    for raw in extra_service_ids or []:
        sid = int(raw)
        if sid != service.id and sid not in ids:
            ids.append(sid)
    if len(ids) > MAX_EXTRA_SERVICES:
        raise ValueError(f"Bir tashrifda asosiy xizmatdan tashqari {MAX_EXTRA_SERVICES} tadan ko'p xizmat tanlab bo'lmaydi")
    extras = list(Service.objects.filter(pk__in=ids, shop_id=service.shop_id, is_active=True))
    if len(extras) != len(ids):
        raise ValueError("Qo'shimcha xizmat topilmadi yoki boshqa sartaroshxonaga tegishli")
    by_id = {s.id: s for s in extras}
    return [by_id[i] for i in ids]


def _totals(service: Service, extras: list[Service]) -> tuple[int, int]:
    """(umumiy davomiylik daqiqa, umumiy narx so'm)."""
    return (service.duration_minutes + sum(s.duration_minutes for s in extras),
            int(service.price) + sum(int(s.price) for s in extras))


def get_available_slots(user, master_id: int, service_id: int, date: str,
                        extra_service_ids: list[int] | None = None) -> dict:
    day = _parse_date(date)
    master = Master.objects.select_related("user", "shop").get(pk=master_id, is_active=True)
    service = Service.objects.get(pk=service_id, is_active=True)
    extras = _resolve_extras(service, extra_service_ids)
    minutes, _ = _totals(service, extras)
    return {
        "master": _master_name(master),
        "service": " + ".join([service.name] + [s.name for s in extras]),
        "date": date,
        "duration_minutes": minutes,
        "slots": _get_slots(master, service, day, duration_minutes=minutes),
    }


def find_best_slots(
        user,
        service_id: int,
        date: str,
        master_id: int | None = None,
        part_of_day: str | None = None,
        preferred_time: str | None = None,
        search_days: int = 3,
        limit: int = 5,
        extra_service_ids: list[int] | None = None,
) -> dict:
    """Xizmat uchun eng mos bo'sh vaqtlarni topadi (usta tanlanmasa, hamma ustalar bo'yicha).

    date dan boshlab search_days kun ichida qidiradi: sana so'ralgan kundan farq qilishi mumkin.
    part_of_day: morning | afternoon | evening, preferred_time: 'HH:MM'.
    """
    start_day = _parse_date(date)
    part_of_day = part_of_day or None
    if part_of_day is not None and part_of_day not in PARTS_OF_DAY:
        raise ValueError("part_of_day faqat morning, afternoon yoki evening bo'lishi mumkin")
    preferred = _parse_time(preferred_time) if preferred_time else None
    search_days = max(1, min(int(search_days or 1), 7))

    service = Service.objects.select_related("shop").get(pk=service_id, is_active=True)
    masters = Master.objects.filter(shop_id=service.shop_id, is_active=True).select_related("user", "shop")
    if master_id:
        masters = masters.filter(pk=master_id)
        if not masters:
            raise ValueError("Bu usta ushbu xizmat sartaroshxonasida topilmadi")

    extras = _resolve_extras(service, extra_service_ids)
    minutes, total_price = _totals(service, extras)
    names = {m.id: _master_name(m) for m in masters}
    candidates = []
    for offset in range(search_days):
        day = start_day + timedelta(days=offset)
        for m in masters:
            for hhmm in _get_slots(m, service, day, duration_minutes=minutes):
                candidates.append((day, m.id, hhmm))

    best = rank_slots(
        candidates,
        window=PARTS_OF_DAY.get(part_of_day),
        preferred=preferred,
        limit=limit,
    )
    suggestions = []
    for d, mid, hhmm in best:
        start_local = datetime.combine(d, _parse_time(hhmm), tzinfo=SHOP_TZ)
        pct = pricing.discount_percent(service.shop_id, start_local)
        suggestions.append({
            "date": d.isoformat(), "start_time": hhmm, "master_id": mid, "master": names[mid],
            "price": pricing.apply_discount(total_price, pct), "discount_percent": pct,
        })
    return {
        "service": service.name,
        "shop": service.shop.name,
        "base_price": total_price,
        "duration_minutes": minutes,
        "requested_date": date,
        "searched_days": search_days,
        "suggestions": suggestions,
    }


# ------------------------------------------------------------------ yozish

def create_booking(user, master_id: int, service_id: int, date: str, start_time: str,
                   promo_code: str = "", certificate_code: str = "",
                   extra_service_ids: list[int] | None = None) -> dict:
    """Bron yaratadi. Mijoz HAR DOIM so'rov yuborgan foydalanuvchi (model emas!).

    promo_code / certificate_code ixtiyoriy; noto'g'ri bo'lsa bron YARATILMAYDI va xato qaytadi."""
    if user.blocked_until and user.blocked_until > timezone.now():
        return {"error": "Sizning hisobingiz vaqtincha bloklangan, bron qilib bo'lmaydi."}

    day = _parse_date(date)
    start = _parse_time(start_time)

    with transaction.atomic():
        # Ikkita bir vaqtdagi so'rov bir slotni olmasligi uchun ustani qulflaymiz
        master = Master.objects.select_for_update().get(pk=master_id, is_active=True)
        master = Master.objects.select_related("user", "shop").get(pk=master.pk)
        service = Service.objects.get(pk=service_id, is_active=True)

        extras = _resolve_extras(service, extra_service_ids)
        minutes, _total = _totals(service, extras)
        if start_time not in _get_slots(master, service, day, duration_minutes=minutes):
            return {"error": "Bu vaqt band yoki ish vaqtidan tashqarida. Boshqa vaqt tanlang."}

        start_dt = datetime.combine(day, start, tzinfo=SHOP_TZ)
        end_dt = start_dt + timedelta(minutes=minutes)
        try:
            quote = promotions.quote(user, service, start_dt, promo_code, certificate_code, lock=True,
                                     extra_price=sum(int(s.price) for s in extras))
        except promotions.PromotionError as exc:
            return {"error": str(exc)}
        booking = Booking.objects.create(
            client=user,
            master=master,
            service=service,
            start_time=start_dt,
            end_time=end_dt,
            price=quote.final_price,
            status=Booking.Status.PENDING,
            discount_amount=quote.discount_amount,
            promo_code=quote.promo,
            loyalty_applied=quote.loyalty_applied,
            certificate=quote.certificate,
            certificate_amount=quote.certificate_amount,
        )
        if extras:
            booking.extra_services.set(extras)
        # Kutish ro'yxatida turgan bo'lsa, endi bron qilingan
        WaitlistEntry.objects.filter(
            client=user, service=service, date=day,
            status__in=[WaitlistEntry.Status.WAITING, WaitlistEntry.Status.NOTIFIED],
        ).update(status=WaitlistEntry.Status.BOOKED)
        booking_events.notify_master_new(booking)

    return {
        "booking_id": booking.id,
        "shop": master.shop.name,
        "master": _master_name(master),
        "service": " + ".join([service.name] + [s.name for s in extras]),
        "duration_minutes": minutes,
        "price": quote.final_price,
        "base_price": quote.base_price,
        "discount_percent": quote.discount_percent,
        "discount_kind": quote.discount_kind,
        "promo_code": quote.promo.code if quote.promo else None,
        "loyalty_applied": quote.loyalty_applied,
        "certificate_amount": quote.certificate_amount,
        "notes": quote.notes,
        "date": date,
        "start_time": start_time,
        "end_time": end_dt.strftime("%H:%M"),
        "status": "pending",
    }


def my_recommendations(user) -> dict:
    """Mijoz tarixiga asoslangan tavsiya: sevimli usta/xizmat, oxirgi tashrif."""
    return client_profile(user)


def my_bookings(user, upcoming_only: bool = True) -> dict:
    """Mijozning o'z bronlari (faqat uniki: user tool'ga closure orqali bog'langan)."""
    return {"bookings": booking_services.list_my_bookings(user, upcoming_only=upcoming_only)}


def cancel_booking(user, booking_id: int) -> dict:
    """Mijoz o'z bronini bekor qiladi (qoidalar bookings.services da)."""
    return booking_services.cancel_by_client(user, booking_id)


# ---------------------------------------------------------------- ko'chirish, kutish, narx, navbat, doimiy bron

def reschedule_booking(user, booking_id: int, date: str, start_time: str, master_id: int | None = None) -> dict:
    """Mijoz bronini boshqa vaqtga ko'chiradi (bekor qilish qoidalari amal qiladi)."""
    return booking_services.reschedule_by_client(user, booking_id, date, start_time, master_id=master_id or None)


def join_waitlist(user, service_id: int, date: str, master_id: int | None = None,
                  from_time: str | None = None, to_time: str | None = None) -> dict:
    """Vaqt band bo'lsa kutish ro'yxatiga yozadi: bo'shaganda mijozga Telegram xabar boradi."""
    from apps.bookings import waitlist

    day = _parse_date(date)
    service = Service.objects.get(pk=service_id, is_active=True)
    master = Master.objects.get(pk=master_id, is_active=True) if master_id else None
    entry = waitlist.join(user, service, day, master=master,
                          from_time=_parse_time(from_time) if from_time else None,
                          to_time=_parse_time(to_time) if to_time else None)
    return waitlist.entry_to_dict(entry)


def quote_price(user, service_id: int, date: str, start_time: str, promo_code: str = "",
                certificate_code: str = "", extra_service_ids: list[int] | None = None) -> dict:
    """Bron yaratmasdan yakuniy narxni hisoblaydi (chegirma, promokod, sertifikat)."""
    service = Service.objects.get(pk=service_id, is_active=True)
    extras = _resolve_extras(service, extra_service_ids)
    minutes, total = _totals(service, extras)
    start_dt = datetime.combine(_parse_date(date), _parse_time(start_time), tzinfo=SHOP_TZ)
    q = promotions.quote(user, service, start_dt, promo_code, certificate_code,
                         extra_price=sum(int(s.price) for s in extras))
    return {"service": " + ".join([service.name] + [s.name for s in extras]), "duration_minutes": minutes,
            "base_price": q.base_price, "discount_amount": q.discount_amount, "discount_percent": q.discount_percent,
            "discount_kind": q.discount_kind, "certificate_amount": q.certificate_amount,
            "final_price": q.final_price, "notes": q.notes}


def join_queue(user, shop_id: int, service_id: int, master_id: int | None = None) -> dict:
    """Hoziroq kelmoqchi bo'lgan mijozni jonli navbatga qo'yadi; kutish vaqtini qaytaradi."""
    from apps.bookings import queue

    return queue.join(user, shop_id, service_id, master_id or None)


def queue_status(user) -> dict:
    from apps.bookings import queue

    return queue.my_ticket(user) or {"status": "none", "message": "Siz navbatda emassiz"}


def leave_queue(user) -> dict:
    from apps.bookings import queue

    return queue.leave(user)


def create_recurring_booking(user, master_id: int, service_id: int, date: str, start_time: str,
                             every_weeks: int = 2, end_date: str | None = None) -> dict:
    """Doimiy bron: shu usta, shu hafta kuni va soat, har N haftada. Birinchi uchrashuv darhol bron qilinadi."""
    from apps.bookings import recurring

    return recurring.create(user, master_id, service_id, _parse_date(date), _parse_time(start_time),
                            every_weeks, _parse_date(end_date) if end_date else None)


def my_recurring(user) -> dict:
    from apps.bookings import recurring

    return {"recurring": recurring.list_mine(user)}


def stop_recurring(user, recurring_id: int) -> dict:
    from apps.bookings import recurring

    return recurring.stop(user, recurring_id)
