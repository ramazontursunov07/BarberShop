"""LLM bilan muloqot sikli (tool calling).

OpenAI-mos API ishlatiladi, shuning uchun bitta kod bilan bepul provayderlar
(Groq, Google Gemini, OpenRouter) va lokal Ollama ishlaydi.
"""
import json
from datetime import date

from .llm import conf, get_client
from .tools import TOOLS, run_tool

MAX_STEPS = 6  # cheksiz tsiklning oldini olish


def _openai_tools() -> list[dict]:
    """tools.py dagi sxemalarni OpenAI formatiga o'giramiz."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]


def _system_prompt() -> str:
    return (
        "Sen sartaroshxonalar uchun bron qilish yordamchisisan. "
        "Foydalanuvchi bilan o'zbek tilida (u rus tilida yozsa, rus tilida) muloqot qil. "
        f"Bugungi sana: {date.today().isoformat()} ({date.today().strftime('%A')}). "
        "'Ertaga', 'dushanba kuni' kabi so'zlarni aniq sanaga aylantir.\n"
        "Qoidalar:\n"
        "1. ID larni o'zing o'ylab topma, faqat tool natijalaridan ol.\n"
        "2. Narx va davomiylik uchun list_services, ustalar uchun list_masters ni ishlat.\n"
        "3. Qoidalar (bekor qilish, kechikish, to'lov), qulayliklar, usta haqida ma'lumot va "
        "mijoz sharhlari haqidagi savollarga FAQAT search_shop_info natijasiga tayanib javob ber. "
        "Natijada javob bo'lmasa, 'bu haqda ma'lumotim yo'q' de, taxmin qilma.\n"
        "4. Bo'sh vaqtlarni faqat get_available_slots yoki find_best_slots orqali tekshir.\n"
        "5. create_booking ni chaqirishdan oldin usta, xizmat, sana va vaqtni mijozdan aniq tasdiqlat.\n"
        "6. Mijoz noaniq vaqt aytsa ('ertaga kechqurun', 'ertalab', 'soat 3 atrofida') yoki usta aytmasa, "
        "find_best_slots ni ishlat. Natijadan 2-3 ta eng mos vaqtni taklif qil. Agar natijadagi sana "
        "so'ralgan sanadan farq qilsa, buni mijozga aniq ayt. Bo'sh vaqt topilmasa, boshqa kun yoki "
        "vaqtni taklif qil.\n"
        "7. Mijozning bronlarini my_bookings orqali ko'rsat. Bronni bekor qilishdan oldin my_bookings dan id ni ol "
        "va qaysi bronni bekor qilishni mijozdan aniq tasdiqlat, keyin cancel_booking ni chaqir.\n"
        "Javoblar qisqa va xushmuomala bo'lsin."
    )


def run_agent(user, message: str, history: list[dict] | None = None) -> str:
    client = get_client()
    model = conf("LLM_MODEL", "llama-3.3-70b-versatile")
    tools = _openai_tools()

    messages = [{"role": "system", "content": _system_prompt()}]
    messages += list(history or [])
    messages.append({"role": "user", "content": message})

    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            max_tokens=1000,
        )
        msg = resp.choices[0].message

        if not msg.tool_calls:
            return msg.content or ""

        messages.append(
            {
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            }
        )

        for tc in msg.tool_calls:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            output = run_tool(tc.function.name, user, args)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(output, ensure_ascii=False),
                }
            )

    return "Kechirasiz, so'rovni bajara olmadim. Iltimos, qayta urinib ko'ring."
