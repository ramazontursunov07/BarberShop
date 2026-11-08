"""LLM provayderi sozlamalari (chat va embedding uchun umumiy)."""
import os

from django.conf import settings
from openai import OpenAI


def conf(name: str, default: str = "") -> str:
    return os.environ.get(name) or getattr(settings, name, default) or default


def get_client() -> OpenAI:
    return OpenAI(
        api_key=conf("LLM_API_KEY"),
        base_url=conf("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
    )
