"""Gemini 3 modellarini OpenAI-mos rejimda ishlatish uchun moslashtirish.

Muammo: Gemini 3 modellari tool chaqiruvi javobiga `tool_calls[N].extra_content.google.thought_signature`
(modelning ichki fikr izi) qo'shadi va keyingi so'rovda uni qaytarishni talab qiladi. LangChain bu nostandart
maydonni tushirib qoldiradi, natijada Gemini 400 xatosini beradi:
    "Function call is missing a thought_signature in functionCall parts".

Yechim: Google hujjatlashtirgan o'tkazib yuborish qiymatini (`skip_thought_signature_validator`) yo'qolgan
joylarga qo'yamiz. Eslatma: Google ogohlantiradi, imzo bo'lmasa model sifati biroz pasayishi mumkin.
Sof Python: Django va LangChain'ga bog'liq emas, shuning uchun test qilinadi.
"""

BYPASS_SIGNATURE = "skip_thought_signature_validator"


def is_gemini_endpoint(base_url: str | None) -> bool:
    return "generativelanguage.googleapis.com" in (base_url or "")


def add_thought_signature_bypass(messages: list) -> list:
    """Assistant xabarlaridagi har bir tool chaqiruviga, agar imzo bo'lmasa, o'tkazib yuborish qiymatini qo'yadi.
    Mavjud (haqiqiy) imzolarga tegmaydi. Ro'yxatni joyida o'zgartiradi va qaytaradi."""
    if messages is None:
        return []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            if isinstance(call, dict) and not call.get("extra_content"):
                call["extra_content"] = {"google": {"thought_signature": BYPASS_SIGNATURE}}
    return messages
