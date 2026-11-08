"""Claude bilan muloqot sikli (tool use)."""
import json
from datetime import date

import anthropic
from django.conf import settings

from .tools import TOOLS, run_tool

MAX_STEPS = 6  # cheksiz tsiklning oldini olish


def _system_prompt() -> str:
    return (
        "Sen sartaroshxonalar uchun bron qilish yordamchisisan. "
        "Foydalanuvchi bilan o'zbek tilida (u rus tilida yozsa, rus tilida) muloqot qil. "
        f"Bugungi sana: {date.today().isoformat()} ({date.today().strftime('%A')}). "
        "'Ertaga', 'dushanba kuni' kabi so'zlarni aniq sanaga aylantir. "
        "Qoidalar: ID larni o'zing o'ylab topma, faqat tool natijalaridan ol. "
        "Bo'sh vaqtlarni faqat get_available_slots orqali tekshir. "
        "create_booking ni chaqirishdan oldin usta, xizmat, sana va vaqtni mijozdan aniq tasdiqlat. "
        "Javoblar qisqa va xushmuomala bo'lsin."
    )


def run_agent(user, message: str, history: list[dict] | None = None) -> str:
    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY muhit o'zgaruvchisidan
    model = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-5-5")

    messages = list(history or [])
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_STEPS):
        resp = client.messages.create(
            model=model,
            max_tokens=1000,
            system=_system_prompt(),
            tools=TOOLS,
            messages=messages,
        )

        if resp.stop_reason != "tool_use":
            return "".join(b.text for b in resp.content if b.type == "text")

        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                output = run_tool(block.name, user, block.input)
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(output, ensure_ascii=False),
                    }
                )
        messages.append({"role": "user", "content": results})

    return "Kechirasiz, so'rovni bajara olmadim. Iltimos, qayta urinib ko'ring."
