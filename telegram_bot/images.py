"""Soch turmagi uchun tayyor rasmlar: Pexels (bepul litsenziyali rasmlar) API'sidan qidiriladi.

Kalit `.env` da `PEXELS_API_KEY` (https://www.pexels.com/api/ dan bepul olinadi).
Kalit yo'q yoki qidiruv xato bersa, bot shunchaki matn bilan javob beradi.
"""
import logging

import httpx

logger = logging.getLogger("telegram_bot.images")

PEXELS_URL = "https://api.pexels.com/v1/search"

# Turmak nomidagi kalit so'z -> inglizcha qidiruv (Pexels inglizcha yaxshi ishlaydi). Birinchi mos kelgani olinadi.
QUERIES = [
    ("quiff", "men quiff pompadour haircut"),
    ("crew cut", "men crew cut haircut"),
    ("fade", "men fade haircut"),
    ("soqol", "men short beard haircut"),
    ("bang", "men textured fringe haircut"),
    ("teksturali", "men textured haircut"),
    ("yon tomonga", "men side part haircut"),
    ("klassik", "men classic side part haircut"),
    ("o'rtacha uzunlik", "men medium length haircut"),
]
DEFAULT_QUERY = "men haircut"


def query_for(name: str) -> str:
    low = name.lower().replace("’", "'").replace("‘", "'")
    for key, query in QUERIES:
        if key in low:
            return query
    return DEFAULT_QUERY


async def find_photo(client: httpx.AsyncClient, api_key: str, name: str) -> dict | None:
    """{'url', 'caption'} yoki None."""
    try:
        resp = await client.get(
            PEXELS_URL,
            params={"query": query_for(name), "per_page": 1, "orientation": "portrait"},
            headers={"Authorization": api_key},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        logger.warning("Pexels'ga ulanib bo'lmadi: %s", type(exc).__name__)
        return None
    if resp.status_code != 200:
        logger.warning("Pexels xato: status=%s", resp.status_code)
        return None
    photos = resp.json().get("photos") or []
    if not photos:
        return None
    p = photos[0]
    return {
        "url": p["src"]["large"],
        "caption": f"{name}\nFoto: {p.get('photographer', '')} / Pexels",
    }


async def photos_for(api_key: str, names: list[str]) -> list[dict]:
    if not api_key:
        return []
    async with httpx.AsyncClient() as client:
        found = [await find_photo(client, api_key, n) for n in names]
    return [f for f in found if f]
