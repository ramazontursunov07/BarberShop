"""LangGraph uchun yordamchi funksiyalar (Django va LangChain'ga bog'liq emas)."""


def flatten_content(content) -> str:
    """LLM javobi matn yoki qismlar ro'yxati bo'lishi mumkin: har doim matnga aylantiramiz."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type", "text") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content or "")


def parse_route(text: str) -> str:
    """Router javobidan yo'nalishni oladi. Ishonchsiz bo'lsa 'booking' (xavfsizroq)."""
    t = (text or "").strip().lower()
    if "info" in t and "booking" not in t:
        return "info"
    return "booking"


def _text(message) -> str:
    return flatten_content(getattr(message, "content", "")).strip()


def last_user_text(messages) -> str:
    for m in reversed(messages):
        if getattr(m, "type", None) == "human":
            return _text(m)
    return ""


def transcript(messages, limit: int = 6) -> str:
    """Oxirgi xabarlarni 'Mijoz: ... / Yordamchi: ...' ko'rinishida matnga aylantiradi."""
    lines = []
    for m in messages:
        kind = getattr(m, "type", None)
        text = _text(m)
        if not text:
            continue
        if kind == "human":
            lines.append(f"Mijoz: {text}")
        elif kind == "ai":
            lines.append(f"Yordamchi: {text}")
    return "\n".join(lines[-limit:])


def make_query(messages, short_len: int = 25) -> str:
    """Qidiruv so'rovi: qisqa savol ('Bekor qilsam-chi?') oldingi savol bilan birlashtiriladi."""
    humans = [_text(m) for m in messages if getattr(m, "type", None) == "human"]
    humans = [h for h in humans if h]
    if not humans:
        return ""
    last = humans[-1]
    if len(last) < short_len and len(humans) > 1:
        return f"{humans[-2]} {last}"
    return last


EMPTY_NUDGE = (
    "Oldingi javobing bo'sh edi. Tool natijalariga asoslanib mijozga uning tilida qisqa javob yoz "
    "yoki kerakli tool'ni chaqir."
)

FALLBACK_UZ = "Kechirasiz, javob tayyorlay olmadim. Iltimos, qayta urinib ko'ring."
FALLBACK_RU = "Извините, не удалось подготовить ответ. Пожалуйста, попробуйте ещё раз."
BUSY_UZ = "Bu so'rov juda uzoq davom etdi. Iltimos, «mening bronlarim» deb yozib, natijani tekshiring."
BUSY_RU = "Запрос занял слишком много времени. Напишите «мои записи», чтобы проверить результат."


def is_russian(text: str) -> bool:
    letters = [c for c in (text or "") if c.isalpha()]
    if not letters:
        return False
    cyr = sum(1 for c in letters if "\u0400" <= c <= "\u04ff")
    return cyr / len(letters) > 0.5


def fallback_reply(user_text: str, busy: bool = False) -> str:
    """Model javob bera olmaganda mijoz tilida xabar (rus tilida yozgan mijozga rus tilida)."""
    ru = is_russian(user_text)
    if busy:
        return BUSY_RU if ru else BUSY_UZ
    return FALLBACK_RU if ru else FALLBACK_UZ


def invoke_nonempty(invoke, messages, nudge_message, retries: int = 2):
    """Ba'zi modellar (Gemini flash-lite) tool natijasidan keyin bo'sh javob qaytaradi.
    Bo'sh javob (matn ham, tool chaqiruvi ham yo'q) kelsa, ogohlantirish bilan qayta so'raydi.
    nudge_message faqat shu so'rovga qo'shiladi, graf holatiga tushmaydi."""
    resp = invoke(messages)
    for _ in range(retries):
        if getattr(resp, "tool_calls", None) or flatten_content(getattr(resp, "content", "")).strip():
            break
        resp = invoke([*messages, nudge_message])
    return resp
