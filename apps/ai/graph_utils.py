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
