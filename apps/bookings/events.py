
"""Bron hodisalari haqida Telegram xabarlari: ustaga (yangi bron, bekor, ko'chirish) va mijozga (usta bekor qilsa).

Hammasi tranzaksiya muvaffaqiyatli tugagandan keyin (on_commit) va xato bo'lsa ham asosiy amalni buzmasdan ishlaydi.
Telegram'ga ulanmagan (telegram_id yo'q) foydalanuvchilarga xabar yuborilmaydi.
"""
import logging

from django.db import transaction

from .services import SHOP_TZ, master_name, services_label

logger = logging.getLogger(__name__)


def _send(user, text: str) -> bool:
    if user is None or not getattr(user, "telegram_id", None):
        return False
    from apps.ai.notify import send_telegram  # lazy: httpx/llm sozlamalari faqat kerak bo'lganda

    return send_telegram(user.telegram_id, text)


def _after_commit(fn, *args) -> None:
    def run():
        try:
            fn(*args)
        except Exception:
            logger.exception("Bron xabarini yuborib bo'lmadi")

    transaction.on_commit(run)


def when(booking) -> str:
    start = booking.start_time.astimezone(SHOP_TZ)
    return f"{start:%d.%m} soat {start:%H:%M}"


def _client_line(booking) -> str:
    c = booking.client
    return f"{c.first_name} {c.last_name}".strip() + f" ({c.phone})"


# ------------------------------------------------------------------ ustaga

def notify_master_new(booking) -> None:
    _after_commit(lambda: _send(
        booking.master.user,
        f"🆕 Yangi bron: {when(booking)}\n{_client_line(booking)}\n{services_label(booking)}, {int(booking.price):,} so'm".replace(",", " "),
    ))


def notify_master_cancelled(booking) -> None:
    _after_commit(lambda: _send(
        booking.master.user,
        f"❌ Bron bekor qilindi: {when(booking)}\n{_client_line(booking)}, {services_label(booking)}",
    ))


def notify_master_rescheduled(booking, old_when: str, old_master_user=None) -> None:
    """old_master_user: bron boshqa ustaga ko'chirilgan bo'lsa, eski ustaga ham xabar boradi."""
    def run():
        _send(booking.master.user,
              f"🔁 Bron ko'chirildi: {old_when} dan {when(booking)} ga\n{_client_line(booking)}, {services_label(booking)}")
        if old_master_user is not None and old_master_user.id != booking.master.user_id:
            _send(old_master_user, f"❌ Bron boshqa ustaga ko'chirildi: {old_when}\n{_client_line(booking)}")

    _after_commit(run)


# ------------------------------------------------------------------ mijozga

def notify_client_cancelled_by_staff(booking) -> None:
    _after_commit(lambda: _send(
        booking.client,
        f"Kechirasiz, {booking.master.shop.name}da {when(booking)} dagi broningiz ({services_label(booking)}, "
        f"usta {master_name(booking.master)}) sartaroshxona tomonidan bekor qilindi.\n"
        f"Yangi vaqt tanlash uchun botga yozing, masalan: «ertaga kechqurun {booking.service.name.lower()}».",
    ))


def notify_client_day_off(booking, reason: str = "") -> None:
    why = f" ({reason})" if reason else ""
    _after_commit(lambda: _send(
        booking.client,
        f"Kechirasiz, usta {master_name(booking.master)} {when(booking)} da ishlay olmaydi{why}, "
        f"shuning uchun broningiz ({services_label(booking)}) bekor qilindi.\n"
        f"Boshqa vaqt yoki boshqa usta tanlash uchun botga yozing, masalan: «ertaga kechqurun {booking.service.name.lower()}».",
    ))


def notify_client_called(ticket) -> None:
    _after_commit(lambda: _send(
        ticket.client,
        f"✅ Navbatingiz keldi! {ticket.shop.name}da usta {master_name(ticket.master)} sizni kutyapti "
        f"({ticket.service.name}).",
    ))
    