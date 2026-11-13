"""Ovozli xabarni matnga aylantirish (speech-to-text).

OpenAI-mos /audio/transcriptions endpointi ishlatiladi (Groq whisper-large-v3 yoki OpenAI whisper).
Kalit alohida: STT_API_KEY. Uni ataylab LLM_API_KEY ga ulamaymiz, aks holda chat provayderi (Gemini)
kaliti boshqa provayderga yuborilib qolardi.

.env sozlamalari:
    STT_API_KEY=...                                   (majburiy)
    STT_BASE_URL=https://api.groq.com/openai/v1       (standart)
    STT_MODEL=whisper-large-v3                        (standart)
    STT_LANGUAGE=                                     (bo'sh = avtomatik; o'zbek/rus aralash uchun shunday qoldiring)
"""
import os
import re

from openai import OpenAI

from . import observability
from .llm import conf

MAX_AUDIO_BYTES = 2 * 1024 * 1024  # Telegram ovozli xabari (60 s) odatda 1 MB dan kichik
ALLOWED_EXTENSIONS = {"ogg", "oga", "mp3", "wav", "m4a", "webm", "mp4", "mpeg", "mpga", "flac"}
MAX_TEXT_CHARS = 1000  # chat API xabar chegarasi bilan bir xil

# Whisper'ga mavzu so'zlarini bildiradi: "soch olish", "soqol" kabi so'zlarni to'g'riroq taniydi
HINT_PROMPT = "Sartaroshxona bron: soch olish, soqol olish, ertaga, kechqurun, ertalab, usta, Jasur, Bobur."


class SpeechNotConfigured(Exception):
    """STT_API_KEY sozlanmagan."""


class EmptyTranscript(Exception):
    """Ovozdan matn chiqmadi (jimlik yoki tushunib bo'lmadi)."""


def safe_filename(name: str | None) -> str:
    """Faqat ruxsat etilgan kengaytma qoladi; fayl nomi foydalanuvchidan kelgani uchun tozalanadi."""
    ext = os.path.splitext(name or "")[1].lstrip(".").lower()
    return f"voice.{ext if ext in ALLOWED_EXTENSIONS else 'ogg'}"


def get_stt_client() -> OpenAI:
    api_key = conf("STT_API_KEY")
    if not api_key:
        raise SpeechNotConfigured("STT_API_KEY sozlanmagan")
    return OpenAI(api_key=api_key, base_url=conf("STT_BASE_URL", "https://api.groq.com/openai/v1"))


def transcribe(audio: bytes, filename: str | None = None) -> str:
    client = get_stt_client()
    kwargs = {
        "model": conf("STT_MODEL", "whisper-large-v3"),
        "file": (safe_filename(filename), audio),
        "prompt": HINT_PROMPT,
        "temperature": 0,
    }
    language = conf("STT_LANGUAGE")
    if language:
        kwargs["language"] = language
    with observability.track("stt", "transcribe", kwargs["model"]):
        resp = client.audio.transcriptions.create(**kwargs)
    text = re.sub(r"\s+", " ", getattr(resp, "text", "") or "").strip()
    if not text:
        raise EmptyTranscript()
    return text[:MAX_TEXT_CHARS]
