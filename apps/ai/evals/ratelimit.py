"""429 (limit) xatosini tahlil qilish: kunlik limitmi yoki daqiqalikmi, qancha kutish kerak.

Sof Python (Django va LLM'ga bog'liq emas), shuning uchun test qilinadi.
"""
import re

DEFAULT_DELAY = 60.0
MIN_DELAY = 5.0
MAX_DELAY = 120.0
SAFETY_MARGIN = 2.0


def is_daily_limit(message: str) -> bool:
    """Xato matnida kunlik kvota tilga olinganmi (masalan 'GenerateRequestsPerDayPerProject...')."""
    flat = re.sub(r"[\s_]+", "", (message or "").lower())
    return "perday" in flat or "dailylimit" in flat


def parse_retry_delay(message: str, header: str | None = None) -> float:
    """Necha soniya kutish kerak: avval 'retry-after' sarlavhasi, keyin xabardagi 'retry in 12s' / 'retryDelay: 12s'."""
    delay = None
    if header:
        try:
            delay = float(header)
        except ValueError:
            delay = None
    if delay is None:
        match = re.search(r"retry(?:delay)?\D{0,12}?(\d+(?:\.\d+)?)\s*s", message or "", re.IGNORECASE)
        if match:
            delay = float(match.group(1))
    if delay is None:
        delay = DEFAULT_DELAY
    return min(max(delay, MIN_DELAY), MAX_DELAY) + SAFETY_MARGIN


def describe_error(exc, limit: int = 700) -> str:
    """Xato matni + provayder javobining tanasi.

    Gemini xatolarni ro'yxat shaklida ([{"error": ...}]) qaytaradi, OpenAI kutubxonasi uni o'qiy olmay,
    str(exc) faqat 'Error code: 400' bo'lib qoladi. Haqiqiy sabab javob tanasida bo'ladi.
    """
    text = str(exc)
    body = ""
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            body = response.text
        except Exception:
            body = ""
    if not body:
        raw = getattr(exc, "body", None)
        body = str(raw) if raw else ""
    if body and body not in text:
        text = f"{text} | {body}"
    return " ".join(text.split())[:limit]
