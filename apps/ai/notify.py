"""Mijozlarga Telegram orqali avtomatik xabar yuborish (eslatma, qaytarish).

Bot jarayonidan mustaqil: Telegram Bot API'ga to'g'ridan-to'g'ri murojaat qiladi,
shuning uchun cron/management command'dan chaqirish mumkin.
"""
import logging
import time

import httpx

from .llm import conf

logger = logging.getLogger(__name__)


def reminder_markup(booking_id: int, with_late: bool = True) -> dict:
    """Eslatma tagidagi tugmalar. callback_data: rem:<bron_id>:<c|l|x> (bot shuni qayta ishlaydi)."""
    rows = [[{"text": "✅ Kelaman", "callback_data": f"rem:{booking_id}:c"}]]
    if with_late:
        rows.append([{"text": "⏱ 10 daqiqa kechikaman", "callback_data": f"rem:{booking_id}:l"}])
    rows.append([{"text": "❌ Bekor qilaman", "callback_data": f"rem:{booking_id}:x"}])
    return {"inline_keyboard": rows}


MAX_ATTEMPTS = 3
MAX_WAIT = 5.0  # soniya: so'rov ichida (on_commit) uzoq kutib qolmaslik uchun


def _mark_blocked(chat_id: int) -> None:
    from apps.users.models import User

    User.objects.filter(telegram_id=chat_id).update(telegram_blocked=True)


def _is_blocked(chat_id: int) -> bool:
    from apps.users.models import User

    return User.objects.filter(telegram_id=chat_id, telegram_blocked=True).exists()


def send_telegram(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    """Xabar yuboradi. Vaqtinchalik xatolarda (429, 5xx, tarmoq) qisqa kutib qayta urinadi.

    403 (mijoz botni bloklagan) bo'lsa foydalanuvchi belgilanadi va keyingi xabarlar yuborilmaydi;
    mijoz botga qayta yozganda belgi olib tashlanadi.
    """
    token = conf("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN sozlanmagan")
        return False
    if _is_blocked(chat_id):
        return False
    payload = {"chat_id": chat_id, "text": text, **({"reply_markup": reply_markup} if reply_markup else {})}
    for attempt in range(1, MAX_ATTEMPTS + 1):
        wait = 0.5 * attempt
        try:
            resp = httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=15)
        except httpx.HTTPError as exc:
            # Xato matnida URL (ya'ni token) bo'lishi mumkin, shuning uchun faqat turini yozamiz
            logger.warning("Telegram'ga ulanib bo'lmadi (%s/%s): %s", attempt, MAX_ATTEMPTS, type(exc).__name__)
        else:
            if resp.status_code == 200:
                return True
            if resp.status_code == 403:
                logger.warning("Mijoz botni bloklagan, belgilandi: chat=%s", chat_id)
                _mark_blocked(chat_id)
                return False
            if resp.status_code != 429 and resp.status_code < 500:
                logger.warning("Telegram xabar yubormadi: status=%s chat=%s", resp.status_code, chat_id)
                return False  # 400 va shunga o'xshash: qayta urinish foydasiz
            if resp.status_code == 429:
                try:
                    wait = float(resp.json().get("parameters", {}).get("retry_after", wait))
                except (ValueError, TypeError):
                    pass
            logger.warning("Telegram vaqtinchalik xato: status=%s (%s/%s)", resp.status_code, attempt, MAX_ATTEMPTS)
        if attempt < MAX_ATTEMPTS:
            time.sleep(min(wait, MAX_WAIT))
    return False
