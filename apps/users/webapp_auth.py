"""Telegram Mini App (WebApp) initData imzosini tekshirish. Faqat standart kutubxona.

Hujjat: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

MAX_AGE_SECONDS = 24 * 60 * 60  # initData shundan eski bo'lsa qabul qilinmaydi


class InitDataError(ValueError):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int = MAX_AGE_SECONDS, now: float | None = None) -> dict:
    """initData to'g'ri bo'lsa Telegram foydalanuvchisini (dict: id, first_name, ...) qaytaradi."""
    if not bot_token:
        raise InitDataError("Bot tokeni sozlanmagan")

    pairs = dict(parse_qsl(init_data or "", keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("initData noto'g'ri")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InitDataError("initData imzosi noto'g'ri")

    try:
        auth_date = int(pairs.get("auth_date", ""))
    except ValueError:
        raise InitDataError("initData noto'g'ri")
    if (now if now is not None else time.time()) - auth_date > max_age:
        raise InitDataError("initData eskirgan, Mini App'ni qayta oching")

    try:
        user = json.loads(pairs["user"])
    except (KeyError, json.JSONDecodeError):
        raise InitDataError("initData ichida foydalanuvchi yo'q")
    if not isinstance(user, dict) or not isinstance(user.get("id"), int):
        raise InitDataError("initData ichida foydalanuvchi yo'q")
    return user
