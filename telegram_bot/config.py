"""Bot sozlamalari: loyiha ildizidagi .env fayldan o'qiladi."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@dataclass(frozen=True)
class Settings:
    bot_token: str
    bot_secret: str
    api_base_url: str


def load_settings() -> Settings:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    secret = os.getenv("TELEGRAM_BOT_SECRET", "").strip()
    if not token:
        raise SystemExit(".env da TELEGRAM_BOT_TOKEN yo'q (@BotFather dan oling)")
    if not secret:
        raise SystemExit(".env da TELEGRAM_BOT_SECRET yo'q (Django bilan bir xil bo'lishi kerak)")
    return Settings(
        bot_token=token,
        bot_secret=secret,
        api_base_url=os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
    )
