"""Matnni ovozga aylantirish (text-to-speech): AI javobini ovozli qilish.

Provayderlar (.env):
    TTS_PROVIDER=gemini        # gemini | openai | (bo'sh = o'chiq; brauzer ovozi zaxira bo'ladi)
    TTS_API_KEY=...            # gemini'da bo'sh qolsa va LLM_BASE_URL Google'niki bo'lsa, LLM_API_KEY ishlatiladi
    TTS_MODEL=                 # gemini: gemini-2.5-flash-preview-tts (standart) | openai: gpt-4o-mini-tts / tts-1
    TTS_VOICE=                 # gemini: Kore (standart) | openai: alloy (standart)
    TTS_BASE_URL=              # faqat openai-mos serverlar uchun (standart https://api.openai.com/v1)

Kalit alohida: chat kaliti boshqa provayderga yuborilib qolmasligi uchun (STT dagi qoida bilan bir xil).
Gemini ovozni xom PCM qaytaradi — biz uni WAV'ga o'raymiz. Boshqa format (ogg/mp3) kerak bo'lsa, serverda
ffmpeg bo'lishi shart; OpenAI esa mp3 va opus'ni o'zi beradi.
"""
import base64
import io
import re
import shutil
import subprocess
import wave

import httpx

from . import observability
from .llm import conf

MAX_TTS_CHARS = 600  # uzun matn qimmat va sekin; ovozga faqat boshi aytiladi
TIMEOUT = 40.0
FORMATS = {"wav": "audio/wav", "mp3": "audio/mpeg", "ogg": "audio/ogg"}


class TTSNotConfigured(Exception):
    """TTS_PROVIDER yoki kalit sozlanmagan."""


class TTSFailed(Exception):
    """Provayder xato qaytardi yoki ovoz chiqmadi."""


def clean_text(text: str) -> str:
    """Ovoz uchun matnni tozalaydi: markdown belgilari, havolalar va emoji aytilmasin."""
    text = re.sub(r"```.*?```", " ", text or "", flags=re.S)
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)          # [matn](havola) -> matn
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[*_`#>~|]+", "", text)
    text = re.sub(r"^\s*[-•]\s+", "", text, flags=re.M)
    text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿️]", "", text)  # emoji
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_TTS_CHARS:
        cut = text[:MAX_TTS_CHARS]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        text = cut[: end + 1] if end > 200 else cut
    return text


def provider() -> str:
    return (conf("TTS_PROVIDER") or "").strip().lower()


def is_configured() -> bool:
    try:
        _settings()
    except TTSNotConfigured:
        return False
    return True


def _settings() -> dict:
    name = provider()
    if name not in ("gemini", "openai"):
        raise TTSNotConfigured("TTS_PROVIDER sozlanmagan")
    key = conf("TTS_API_KEY")
    if not key and name == "gemini" and "googleapis.com" in conf("LLM_BASE_URL"):
        key = conf("LLM_API_KEY")
    if not key:
        raise TTSNotConfigured("TTS_API_KEY sozlanmagan")
    if name == "gemini":
        return {"provider": name, "key": key, "model": conf("TTS_MODEL", "gemini-2.5-flash-preview-tts"),
                "voice": conf("TTS_VOICE", "Kore")}
    return {"provider": name, "key": key, "model": conf("TTS_MODEL", "gpt-4o-mini-tts"),
            "voice": conf("TTS_VOICE", "alloy"),
            "base": conf("TTS_BASE_URL", "https://api.openai.com/v1").rstrip("/")}


def _pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _gemini(text: str, cfg: dict) -> tuple[bytes, str]:
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{cfg['model']}:generateContent",
        headers={"x-goog-api-key": cfg["key"]},
        json={
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg["voice"]}}},
            },
        },
        timeout=TIMEOUT,
    )
    if resp.status_code == 429:
        raise TTSFailed("limit")
    if resp.status_code != 200:
        raise TTSFailed(f"gemini {resp.status_code}: {resp.text[:200]}")
    try:
        part = resp.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
        pcm = base64.b64decode(part["data"])
    except (KeyError, IndexError, ValueError, TypeError) as exc:
        raise TTSFailed("gemini: ovoz qaytmadi") from exc
    match = re.search(r"rate=(\d+)", part.get("mimeType", ""))
    return _pcm_to_wav(pcm, int(match.group(1)) if match else 24000), "audio/wav"


def _openai(text: str, cfg: dict, fmt: str) -> tuple[bytes, str]:
    native = "opus" if fmt == "ogg" else "mp3"  # OpenAI "opus" = Ogg konteynerdagi Opus (Telegram ovozli xabari uchun mos)
    resp = httpx.post(
        f"{cfg['base']}/audio/speech",
        headers={"Authorization": f"Bearer {cfg['key']}"},
        json={"model": cfg["model"], "voice": cfg["voice"], "input": text, "response_format": native},
        timeout=TIMEOUT,
    )
    if resp.status_code == 429:
        raise TTSFailed("limit")
    if resp.status_code != 200 or not resp.content:
        raise TTSFailed(f"openai {resp.status_code}: {resp.text[:200]}")
    return resp.content, FORMATS["ogg" if fmt == "ogg" else "mp3"]


def _convert(audio: bytes, fmt: str) -> bytes:
    """WAV -> mp3/ogg (ffmpeg kerak)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise TTSFailed("ffmpeg o'rnatilmagan")
    codec = ["-c:a", "libopus", "-b:a", "32k", "-f", "ogg"] if fmt == "ogg" else ["-c:a", "libmp3lame", "-b:a", "64k", "-f", "mp3"]
    proc = subprocess.run([ffmpeg, "-loglevel", "error", "-i", "pipe:0", *codec, "pipe:1"], input=audio,
                          capture_output=True, timeout=30)
    if proc.returncode != 0 or not proc.stdout:
        raise TTSFailed("ffmpeg xatosi")
    return proc.stdout


def synthesize(text: str, fmt: str = "") -> tuple[bytes, str]:
    """Matnni ovozga aylantiradi. fmt: "" (provayderning o'z formati), "mp3" yoki "ogg". Qaytaradi: (bayt, mime)."""
    cfg = _settings()
    text = clean_text(text)
    if not text:
        raise TTSFailed("matn bo'sh")
    fmt = fmt if fmt in ("mp3", "ogg") else ""
    with observability.track("tts", "speak", cfg["model"]):
        try:
            if cfg["provider"] == "openai":
                return _openai(text, cfg, fmt or "mp3")
            audio, mime = _gemini(text, cfg)
            if fmt:
                return _convert(audio, fmt), FORMATS[fmt]
            return audio, mime
        except httpx.HTTPError as exc:
            raise TTSFailed(f"tarmoq xatosi: {exc.__class__.__name__}") from exc
