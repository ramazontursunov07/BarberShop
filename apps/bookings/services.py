"""Bron biznes-logikasi: REST API ham, AI tool'lari ham shu yerdan foydalanadi.

Shunda qoidalar (bekor qilish muddati, status o'tishlari, bloklash) bitta joyda turadi
va AI agent API'dan farqli qoida bilan ishlab ketmaydi.
"""
from datetime import timedelta
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


def booking_to_dict(b: Booking) -> dict:
    start = b.start_time.astimezone(SHOP_TZ)
    end = b.end_time.astimezone(SHOP_TZ)
    return {
        "id": b.id,
        "shop": b.master.shop.name,
        "master": master_name(b.master),
        "service": b.service.name,
        "price": int(b.price),
        "date": start.strftime("%Y-%m-%d"),
        "start_time": start.strftime("%H:%M"),
        "end_time": end.strftime("%H:%M"),
        "status": b.status,
    }


def _with_relations(qs):
    return qs.select_related("master__user", "master__shop", "service")


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
    return booking_to_dict(booking)


# ------------------------------------------------------------------ usta / egasi

def _can_manage(actor, booking: Booking) -> bool:
    return booking.master.shop.owner_id == actor.id or booking.master.user_id == actor.id


def change_status(actor, booking_id: int, new_status: str) -> dict:
    """Sartaroshxona egasi yoki bronning ustasi holatni o'zgartiradi."""
    if new_status not in Booking.Status.values:
        raise BookingError("Noma'lum status")

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
        booking.save(update_fields=["status"])

        if new_status == Booking.Status.NO_SHOW:
            _register_no_show(booking.client)
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
        