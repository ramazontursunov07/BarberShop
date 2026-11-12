"""Mijozlarga Telegram orqali avtomatik xabar yuborish (eslatma, qaytarish).

Bot jarayonidan mustaqil: Telegram Bot API'ga to'g'ridan-to'g'ri murojaat qiladi,
shuning uchun cron/management command'dan chaqirish mumkin.
"""
import logging

import httpx

from .llm import conf

logger = logging.getLogger(__name__)


def send_telegram(chat_id: int, text: str, reply_markup: dict | None = None) -> bool:
    token = conf("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN sozlanmagan")
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, **({"reply_markup": reply_markup} if reply_markup else {})},
            timeout=15,
        )
    except httpx.HTTPError as exc:
        # Xato matnida URL (ya'ni token) bo'lishi mumkin, shuning uchun faqat turini yozamiz
        logger.warning("Telegram'ga ulanib bo'lmadi: %s", type(exc).__name__)
        return False
    if resp.status_code != 200:
        # 403 = mijoz botni bloklagan; boshqa kodlar vaqtinchalik xato bo'lishi mumkin
        logger.warning("Telegram xabar yubormadi: status=%s chat=%s", resp.status_code, chat_id)
        return False
    return True
