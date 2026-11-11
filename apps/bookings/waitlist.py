"""Kutish ro'yxati: qo'shish va bo'sh joy chiqqanda mijozlarga xabar yuborish."""
import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Booking, WaitlistEntry
from .services import SHOP_TZ, BookingError, master_name

logger = logging.getLogger(__name__)

MAX_ACTIVE_ENTRIES = 5
MAX_DAYS_AHEAD = 30
NOTIFY_LIMIT = 5  # bitta bo'shagan joy uchun eng ko'pi bilan shuncha mijozga xabar
ACTIVE = [WaitlistEntry.Status.WAITING, WaitlistEntry.Status.NOTIFIED]


def entry_to_dict(e: WaitlistEntry) -> dict:
    return {
        "id": e.id,
        "service": e.service.name,
        "shop": e.service.shop.name,
        "master": master_name(e.master) if e.master_id else None,
        "date": e.date.isoformat(),
        "from_time": e.from_time.strftime("%H:%M") if e.from_time else None,
        "to_time": e.to_time.strftime("%H:%M") if e.to_time else None,
        "status": e.status,
    }


def _in_window(entry: WaitlistEntry, hhmm: str) -> bool:
    if entry.from_time and hhmm < entry.from_time.strftime("%H:%M"):
        return False
    if entry.to_time and hhmm >= entry.to_time.strftime("%H:%M"):
        return False
    return True


def _matching_slots(entry: WaitlistEntry, master_filter=None) -> list[tuple]:
    """Yozuvga mos haqiqiy bo'sh vaqtlar: [(master, 'HH:MM'), ...]."""
    from apps.ai import services as availability
    from apps.masters.models import Master

    masters = Master.objects.filter(shop_id=entry.service.shop_id, is_active=True).select_related("user", "shop")
    if entry.master_id:
        masters = masters.filter(pk=entry.master_id)
    found = []
    for m in masters:
        for hhmm in availability._get_slots(m, entry.service, entry.date):
            if _in_window(entry, hhmm):
                found.append((m, hhmm))
    return found


def join(user, service, date, master=None, from_time=None, to_time=None) -> WaitlistEntry:
    if user.blocked_until and user.blocked_until > timezone.now():
        raise BookingError("Sizning hisobingiz vaqtincha bloklangan.")
    today = timezone.now().astimezone(SHOP_TZ).date()
    if date < today:
        raise BookingError("O'tgan sanaga kutish ro'yxatiga yozilib bo'lmaydi")
    if date > today + timedelta(days=MAX_DAYS_AHEAD):
        raise BookingError(f"Kutish ro'yxati faqat {MAX_DAYS_AHEAD} kun oldinga ochiq")
    if master is not None and master.shop_id != service.shop_id:
        raise BookingError("Bu usta tanlangan xizmat sartaroshxonasiga tegishli emas")
    if from_time and to_time and from_time >= to_time:
        raise BookingError("Boshlanish vaqti tugash vaqtidan oldin bo'lishi kerak")

    with transaction.atomic():
        active = WaitlistEntry.objects.filter(client=user, status__in=ACTIVE, date__gte=today)
        if active.count() >= MAX_ACTIVE_ENTRIES:
            raise BookingError(f"Kutish ro'yxatida eng ko'pi bilan {MAX_ACTIVE_ENTRIES} ta yozuv bo'lishi mumkin")
        if active.filter(service=service, master=master, date=date).exists():
            raise BookingError("Siz allaqachon shu vaqtga kutish ro'yxatidasiz")

        entry = WaitlistEntry(client=user, service=service, master=master, date=date,
                              from_time=from_time, to_time=to_time)
        if _matching_slots(entry):
            raise BookingError("Bu vaqtga bo'sh joy bor, kutish shart emas: to'g'ridan-to'g'ri bron qiling")
        entry.save()
    return entry


def leave(user, entry_id: int) -> None:
    updated = WaitlistEntry.objects.filter(pk=entry_id, client=user, status__in=ACTIVE).update(
        status=WaitlistEntry.Status.CANCELLED
    )
    if not updated:
        raise BookingError("Yozuv topilmadi")


def build_message(entry: WaitlistEntry, matches: list[tuple]) -> str:
    master, hhmm = matches[0]
    day = entry.date.strftime("%d.%m")
    return (
        f"🔔 Bo'sh joy chiqdi! {entry.service.shop.name}da {day} kuni soat {hhmm} da "
        f"{master_name(master)} ustaga «{entry.service.name}» uchun joy bo'shadi.\n\n"
        f"Band qilish uchun tezroq yozing: joy birinchi kelganga beriladi."
    )


def notify_freed(booking: Booking) -> int:
    """Bron bekor bo'lib joy bo'shaganda kutayotgan mijozlarga xabar yuboradi (navbat bo'yicha). Yuborilganlar soni."""
    from apps.ai.notify import send_telegram  # lazy: httpx/llm sozlamalari faqat kerak bo'lganda

    local_day = booking.start_time.astimezone(SHOP_TZ).date()
    shop_id = booking.master.shop_id
    entries = (
        WaitlistEntry.objects.filter(
            status=WaitlistEntry.Status.WAITING, date=local_day, service__shop_id=shop_id,
            client__telegram_id__isnull=False,
        )
        .exclude(client=booking.client)
        .select_related("client", "master__user", "service__shop")
        .order_by("created_at")
    )
    sent = 0
    for entry in entries:
        if sent >= NOTIFY_LIMIT:
            break
        matches = _matching_slots(entry)
        if not matches:
            continue
        # Avval belgilaymiz: ikki jarayon bir vaqtda ishlasa ham xabar bir marta ketadi
        claimed = WaitlistEntry.objects.filter(pk=entry.pk, status=WaitlistEntry.Status.WAITING).update(
            status=WaitlistEntry.Status.NOTIFIED, notified_at=timezone.now()
        )
        if not claimed:
            continue
        if send_telegram(entry.client.telegram_id, build_message(entry, matches)):
            sent += 1
        else:
            WaitlistEntry.objects.filter(pk=entry.pk).update(status=WaitlistEntry.Status.WAITING, notified_at=None)
    return sent


def schedule_notify_freed(booking: Booking) -> None:
    """Tranzaksiya muvaffaqiyatli tugagandan keyin chaqiriladi; xato asosiy amalni buzmaydi."""

    def _run():
        try:
            notify_freed(booking)
        except Exception:
            logger.exception("Kutish ro'yxatiga xabar yuborib bo'lmadi (bron %s)", booking.pk)

    transaction.on_commit(_run)
    