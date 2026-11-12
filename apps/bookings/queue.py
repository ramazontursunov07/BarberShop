"""Jonli navbat (walk-in): mijoz "hoziroq kelaman" deydi, taxminiy kutish vaqtini ko'radi; usta "keyingisi"ni chaqiradi."""
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from apps.masters.models import Master
from apps.services.models import Service
from apps.shops.models import Shop

from . import events
from .models import Booking, QueueTicket
from .services import SHOP_TZ, BookingError, BookingForbidden, change_status, master_name

ACTIVE = [QueueTicket.Status.WAITING, QueueTicket.Status.SERVING]


def _active_masters(shop) -> int:
    return max(1, Master.objects.filter(shop=shop, is_active=True).count())


def _ahead(ticket: QueueTicket) -> list[QueueTicket]:
    return list(QueueTicket.objects.filter(shop=ticket.shop, status__in=ACTIVE, created_at__lt=ticket.created_at,
                                           pk__lt=ticket.pk).select_related("service"))


def ticket_to_dict(t: QueueTicket) -> dict:
    ahead = _ahead(t) if t.status == QueueTicket.Status.WAITING else []
    minutes = sum(a.service.duration_minutes for a in ahead) // _active_masters(t.shop)
    return {
        "id": t.id, "shop": t.shop.name, "service": t.service.name, "status": t.status,
        "master": master_name(t.master) if t.master else None,
        "position": len(ahead) + 1 if t.status == QueueTicket.Status.WAITING else 0,
        "people_ahead": len(ahead),
        "estimated_wait_minutes": minutes,
    }


def join(user, shop_id: int, service_id: int, master_id: int | None = None) -> dict:
    shop = Shop.objects.filter(pk=shop_id, is_active=True, is_approved=True).first()
    if not shop:
        raise BookingError("Sartaroshxona topilmadi")
    service = Service.objects.filter(pk=service_id, shop=shop, is_active=True).first()
    if not service:
        raise BookingError("Xizmat topilmadi")
    master = None
    if master_id:
        master = Master.objects.filter(pk=master_id, shop=shop, is_active=True).first()
        if not master:
            raise BookingError("Usta topilmadi")
    now = datetime.now(SHOP_TZ)
    if not (shop.opens_at <= now.time() < shop.closes_at):
        raise BookingError(f"Hozir yopiq. Ish vaqti {shop.opens_at:%H:%M}–{shop.closes_at:%H:%M}. Oldindan bron qiling.")
    with transaction.atomic():
        Shop.objects.select_for_update().get(pk=shop.pk)  # navbat tartibini bir xil saqlash
        if QueueTicket.objects.filter(shop=shop, client=user, status__in=ACTIVE).exists():
            raise BookingError("Siz bu sartaroshxonada allaqachon navbatdasiz")
        t = QueueTicket.objects.create(shop=shop, client=user, service=service, master=master)
    return ticket_to_dict(QueueTicket.objects.select_related("shop", "service", "master__user").get(pk=t.pk))


def my_ticket(user) -> dict | None:
    t = (QueueTicket.objects.filter(client=user, status__in=ACTIVE)
         .select_related("shop", "service", "master__user").first())
    return ticket_to_dict(t) if t else None


def leave(user, ticket_id: int | None = None) -> dict:
    qs = QueueTicket.objects.filter(client=user, status=QueueTicket.Status.WAITING)
    if ticket_id:
        qs = qs.filter(pk=ticket_id)
    t = qs.select_related("shop", "service", "master__user").first()
    if not t:
        raise BookingError("Navbatda turgan joyingiz topilmadi")
    t.status = QueueTicket.Status.CANCELLED
    t.save(update_fields=["status"])
    return {"cancelled": True, "id": t.id}


def _manageable_master(actor, master_id: int) -> Master:
    master = Master.objects.select_related("shop", "user").filter(pk=master_id).first()
    if not master or not (actor.id == master.user_id or actor.id == master.shop.owner_id):
        raise BookingForbidden("Bu ustaga ruxsat yo'q")
    return master


def list_for_staff(actor, shop_id: int) -> list[dict]:
    shop = Shop.objects.filter(pk=shop_id).first()
    if not shop:
        raise BookingError("Sartaroshxona topilmadi")
    if not (shop.owner_id == actor.id or Master.objects.filter(shop=shop, user=actor).exists()):
        raise BookingForbidden("Bu sartaroshxonaga ruxsat yo'q")
    qs = QueueTicket.objects.filter(shop=shop, status__in=ACTIVE).select_related("shop", "service", "master__user", "client")
    out = []
    for t in qs:
        d = ticket_to_dict(t)
        d["client"] = f"{t.client.first_name} {t.client.last_name}".strip()
        d["phone"] = t.client.phone
        out.append(d)
    return out


def call_next(actor, master_id: int) -> dict:
    """Ustaning navbatdagi mijozini chaqiradi: shu zahoti bron (hisobot uchun) yaratiladi."""
    master = _manageable_master(actor, master_id)
    with transaction.atomic():
        Master.objects.select_for_update().get(pk=master.pk)
        if QueueTicket.objects.filter(master_id=master.pk, status=QueueTicket.Status.SERVING).exists():
            raise BookingError("Avval joriy mijozni yakunlang")
        qs = QueueTicket.objects.select_for_update().filter(shop=master.shop, status=QueueTicket.Status.WAITING)
        # shu ustaga atalgan mijoz bo'lsa — birinchi o'sha; bo'lmasa "istalgan usta" navbatdagisi
        t = qs.filter(master=master).first() or qs.filter(master__isnull=True).first()
        if not t:
            raise BookingError("Navbat bo'sh")
        now = timezone.now()
        booking = Booking.objects.create(
            client=t.client, master=master, service=t.service, start_time=now,
            end_time=now + timedelta(minutes=t.service.duration_minutes),
            price=t.service.price, status=Booking.Status.CONFIRMED,
        )
        t.status, t.master, t.started_at, t.booking = QueueTicket.Status.SERVING, master, now, booking
        t.save(update_fields=["status", "master", "started_at", "booking"])
        events.notify_client_called(t)
    return ticket_to_dict(QueueTicket.objects.select_related("shop", "service", "master__user").get(pk=t.pk))


def finish(actor, ticket_id: int, payment_method: str = "") -> dict:
    t = QueueTicket.objects.select_related("master__shop", "master__user").filter(pk=ticket_id).first()
    if not t or t.status != QueueTicket.Status.SERVING or not t.master:
        raise BookingError("Bunday faol navbat topilmadi")
    _manageable_master(actor, t.master_id)
    with transaction.atomic():
        change_status(actor, t.booking_id, Booking.Status.COMPLETED, payment_method=payment_method)
        t.status = QueueTicket.Status.DONE
        t.save(update_fields=["status"])
    return {"id": t.id, "status": t.status}
