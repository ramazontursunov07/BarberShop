"""Bron biznes-logikasi: REST API ham, AI tool'lari ham shu yerdan foydalanadi.

Shunda qoidalar (bekor qilish muddati, status o'tishlari, bloklash) bitta joyda turadi
va AI agent API'dan farqli qoida bilan ishlab ketmaydi.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Booking

SHOP_TZ = ZoneInfo("Asia/Tashkent")

CANCEL_BEFORE = timedelta(hours=2)  # mijoz bronni kamida 2 soat oldin bekor qila oladi
NO_SHOW_STREAK = 3  # ketma-ket shuncha marta kelmasa -> bloklanadi
BLOCK_DAYS = 7

ACTIVE_STATUSES = [Booking.Status.PENDING, Booking.Status.CONFIRMED]

# Usta/egasi o'zgartira oladigan holatlar: joriy holat -> mumkin bo'lgan keyingi holatlar
TRANSITIONS = {
    Booking.Status.PENDING: {Booking.Status.CONFIRMED, Booking.Status.CANCELLED},
    Booking.Status.CONFIRMED: {
        Booking.Status.COMPLETED,
        Booking.Status.NO_SHOW,
        Booking.Status.CANCELLED,
    },
}
# Bu holatlarni faqat bron vaqti boshlangandan keyin qo'yish mumkin
NEEDS_STARTED = {Booking.Status.COMPLETED, Booking.Status.NO_SHOW}


class BookingError(ValueError):
    """Mijoz/usta tushunadigan xato (AI tool'lar ValueError'ni modelga o'qiladigan qilib qaytaradi)."""


class BookingForbidden(Exception):
    """Foydalanuvchining bu bronga huquqi yo'q."""


def master_name(master) -> str:
    user = master.user
    return f"{user.first_name} {user.last_name}".strip() or f"Usta #{master.id}"


def services_label(b: Booking) -> str:
    """"Soch olish + Soqol": asosiy va qo'shimcha xizmatlar bitta qatorda."""
    return " + ".join([b.service.name] + [s.name for s in b.extra_services.all()])


def booking_to_dict(b: Booking) -> dict:
    start = b.start_time.astimezone(SHOP_TZ)
    end = b.end_time.astimezone(SHOP_TZ)
    return {
        "id": b.id,
        "shop": b.master.shop.name,
        "master": master_name(b.master),
        "service": services_label(b),
        "extra_services": [s.name for s in b.extra_services.all()],
        "price": int(b.price),
        "date": start.strftime("%Y-%m-%d"),
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "status": b.status,
    }


def _with_relations(qs):
    return qs.select_related("master__user", "master__shop", "service").prefetch_related("extra_services")


# ------------------------------------------------------------------ mijoz

def list_my_bookings(user, upcoming_only: bool = True, limit: int = 20) -> list[dict]:
    qs = _with_relations(Booking.objects.filter(client=user))
    if upcoming_only:
        qs = qs.filter(status__in=ACTIVE_STATUSES, start_time__gte=timezone.now()).order_by("start_time")
    return [booking_to_dict(b) for b in qs[:limit]]


def cancel_by_client(user, booking_id: int) -> dict:
    """Mijoz o'z bronini bekor qiladi. Boshqa odamning broni 'topilmadi' deb qaytadi."""
    with transaction.atomic():
        booking = (
            _with_relations(Booking.objects.select_for_update())
            .filter(pk=booking_id, client=user)
            .first()
        )
        if booking is None:
            raise BookingError("Bron topilmadi")
        if booking.status not in ACTIVE_STATUSES:
            raise BookingError(f"Bu bronni bekor qilib bo'lmaydi (holati: {booking.status})")
        if booking.start_time - timezone.now() < CANCEL_BEFORE:
            raise BookingError(
                "Bronni kamida 2 soat oldin bekor qilish mumkin. "
                "Iltimos, sartaroshxonaga qo'ng'iroq qiling."
            )
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=["status"])
        _free_slot_hook(booking)
        events.notify_master_cancelled(booking)
    return booking_to_dict(booking)


LATE_OPTIONS = (10, 20, 30)         # mijoz tanlay oladigan kechikish (daqiqa)
LATE_NOTICE_WINDOW = timedelta(hours=3)  # kechikish haqida bron vaqtidan eng ko'pi bilan shuncha oldin xabar beriladi
LATE_GRACE = timedelta(minutes=30)   # bron vaqti o'tgandan keyin ham shuncha vaqt "kechikaman" deyish mumkin


def respond_by_client(user, booking_id: int, action: str, minutes: int = 10) -> dict:
    """Mijoz eslatmadagi tugma orqali javob beradi: action = "confirm" (kelaman) yoki "late" (N daqiqa kechikaman).

    Faqat o'z bronida; boshqa odamning broni "topilmadi" deb qaytadi. Takroriy bosish xavfsiz (idempotent):
    ustaga xabar faqat kechikish vaqti o'zgargandagina boradi. Bekor qilish uchun cancel_by_client ishlatiladi.
    """
    if action not in ("confirm", "late"):
        raise BookingError("Noma'lum amal")
    if action == "late" and minutes not in LATE_OPTIONS:
        raise BookingError(f"Kechikish {', '.join(map(str, LATE_OPTIONS))} daqiqadan biri bo'lishi kerak")

    notify = False
    with transaction.atomic():
        booking = (
            _with_relations(Booking.objects.select_for_update())
            .filter(pk=booking_id, client=user)
            .first()
        )
        if booking is None:
            raise BookingError("Bron topilmadi")
        if booking.status not in ACTIVE_STATUSES:
            raise BookingError(f"Bu bron endi faol emas (holati: {booking.status})")

        now = timezone.now()
        if action == "confirm":
            if booking.start_time <= now:
                raise BookingError("Bron vaqti o'tib bo'lgan")
            if booking.client_confirmed_at is None:
                booking.client_confirmed_at = now
                booking.save(update_fields=["client_confirmed_at"])
        else:
            if booking.start_time - now > LATE_NOTICE_WINDOW:
                raise BookingError("Kechikish haqida bron vaqtiga yaqinroq xabar bering")
            if now - booking.start_time > LATE_GRACE:
                raise BookingError("Bron vaqti o'tib ketgan, iltimos sartaroshxonaga qo'ng'iroq qiling")
            if booking.late_minutes != minutes:
                booking.late_minutes = minutes
                notify = True
            if booking.client_confirmed_at is None:  # kechikaman degan mijoz kelyapti
                booking.client_confirmed_at = now
            booking.save(update_fields=["late_minutes", "client_confirmed_at"])
        if notify:
            events.notify_master_running_late(booking, minutes)
    return {**booking_to_dict(booking), "client_confirmed": True, "late_minutes": booking.late_minutes}


def reschedule_by_client(user, booking_id: int, date: str, start_time: str, master_id: int | None = None) -> dict:
    """Mijoz o'z bronini boshqa vaqtga (xohlasa boshqa ustaga, shu sartaroshxonada) ko'chiradi.

    Qoidalar bekor qilish bilan bir xil: eski vaqtgacha kamida CANCEL_BEFORE qolgan bo'lishi kerak.
    Narx va chegirmalar o'zgarmaydi (qayta hisoblanmaydi).
    """
    # Lazy import: apps.ai.services ham shu modulni import qiladi
    from apps.ai import services as availability
    from apps.masters.models import Master

    try:
        day = availability._parse_date(date)
        start = availability._parse_time(start_time)
    except ValueError as exc:
        raise BookingError(str(exc))

    with transaction.atomic():
        booking = (
            _with_relations(Booking.objects.select_for_update())
            .filter(pk=booking_id, client=user)
            .first()
        )
        if booking is None:
            raise BookingError("Bron topilmadi")
        if booking.status not in ACTIVE_STATUSES:
            raise BookingError(f"Bu bronni ko'chirib bo'lmaydi (holati: {booking.status})")
        if booking.start_time - timezone.now() < CANCEL_BEFORE:
            raise BookingError(
                "Bronni kamida 2 soat oldin ko'chirish mumkin. Iltimos, sartaroshxonaga qo'ng'iroq qiling."
            )

        target = booking.master
        if master_id and master_id != booking.master_id:
            target = Master.objects.filter(pk=master_id, is_active=True, shop_id=booking.master.shop_id).first()
            if target is None:
                raise BookingError("Usta topilmadi")
        # Ustani qulflaymiz: ikki so'rov bir slotni olmasin
        Master.objects.select_for_update().get(pk=target.pk)
        target = Master.objects.select_related("user", "shop").get(pk=target.pk)

        duration = booking.end_time - booking.start_time  # ko'p xizmatli bronda ham umumiy davomiylik saqlanadi
        minutes = int(duration.total_seconds() // 60)
        if start_time not in availability._get_slots(target, booking.service, day, exclude_booking_id=booking.pk,
                                                     duration_minutes=minutes):
            raise BookingError("Bu vaqt band yoki ish vaqtidan tashqarida. Boshqa vaqt tanlang.")

        old_copy = Booking(master=booking.master, client=booking.client, service=booking.service,
                           start_time=booking.start_time, end_time=booking.end_time)
        old_when, old_master_user = events.when(booking), booking.master.user
        new_start = datetime.combine(day, start, tzinfo=SHOP_TZ)
        if new_start <= timezone.now():
            raise BookingError("O'tgan vaqtga ko'chirib bo'lmaydi")
        booking.master = target
        booking.start_time = new_start
        booking.end_time = new_start + duration
        booking.save(update_fields=["master", "start_time", "end_time"])
        # Eslatmalar yangi vaqt uchun qayta yuborilishi kerak
        booking.notifications.all().delete()
        _free_slot_hook(old_copy)
        events.notify_master_rescheduled(booking, old_when, old_master_user)
    return booking_to_dict(booking)


def _free_slot_hook(booking: Booking) -> None:
    """Joy bo'shaganda kutish ro'yxatidagilarga xabar (tranzaksiya tugagach)."""
    from .waitlist import schedule_notify_freed

    schedule_notify_freed(booking)


# ------------------------------------------------------------------ usta / egasi

def _can_manage(actor, booking: Booking) -> bool:
    return booking.master.shop.owner_id == actor.id or booking.master.user_id == actor.id


def change_status(actor, booking_id: int, new_status: str, payment_method: str = "") -> dict:
    """Sartaroshxona egasi yoki bronning ustasi holatni o'zgartiradi.

    payment_method (cash/card/transfer) faqat "bajarildi" holatida beriladi: kassa va usta ulushi hisoboti uchun.
    """
    if new_status not in Booking.Status.values:
        raise BookingError("Noma'lum status")
    if payment_method:
        if new_status != Booking.Status.COMPLETED:
            raise BookingError("To'lov usuli faqat 'bajarilgan' holatida beriladi")
        if payment_method not in Booking.PaymentMethod.values:
            raise BookingError("To'lov usuli: cash, card yoki transfer")

    with transaction.atomic():
        booking = (
            _with_relations(Booking.objects.select_for_update())
            .select_related("client")
            .filter(pk=booking_id)
            .first()
        )
        if booking is None:
            raise BookingError("Bron topilmadi")
        if not _can_manage(actor, booking):
            raise BookingForbidden("Bu bronni boshqarishga huquqingiz yo'q")

        allowed = TRANSITIONS.get(booking.status, set())
        if new_status not in allowed:
            raise BookingError(f"'{booking.status}' holatidan '{new_status}' ga o'tib bo'lmaydi")
        if new_status in NEEDS_STARTED and booking.start_time > timezone.now():
            raise BookingError("Bron vaqti hali boshlanmagan")

        booking.status = new_status
        fields = ["status"]
        if payment_method:
            booking.payment_method = payment_method
            fields.append("payment_method")
        booking.save(update_fields=fields)

        if new_status == Booking.Status.NO_SHOW:
            _register_no_show(booking.client)
        if new_status == Booking.Status.CANCELLED:
            _free_slot_hook(booking)
            if booking.master.user_id != actor.id or booking.master.shop.owner_id == actor.id:
                events.notify_client_cancelled_by_staff(booking)
    return booking_to_dict(booking)


def _register_no_show(client) -> None:
    """Kelmaganlar sonini oshiradi; ketma-ket NO_SHOW_STREAK marta kelmasa vaqtincha bloklaydi."""
    type(client).objects.filter(pk=client.pk).update(no_show_count=F("no_show_count") + 1)
    last = list(
        Booking.objects.filter(
            client=client,
            status__in=[Booking.Status.COMPLETED, Booking.Status.NO_SHOW],
        )
        .order_by("-start_time")
        .values_list("status", flat=True)[:NO_SHOW_STREAK]
    )
    if len(last) == NO_SHOW_STREAK and all(s == Booking.Status.NO_SHOW for s in last):
        type(client).objects.filter(pk=client.pk).update(
            blocked_until=timezone.now() + timedelta(days=BLOCK_DAYS)
        )


# events xabarlari services'dan funksiyalar import qiladi: aylanma importdan saqlanish uchun oxirida
from . import events  # noqa: E402
