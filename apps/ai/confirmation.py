"""Tasdiq to'sig'i: bron yaratish va bekor qilish faqat mijoz AYNAN tasdiqlagandan keyin bajariladi.

Muammo: baholashda model mijozning dastlabki "yozib qo'ying" so'rovini tasdiq deb qabul qilib, darhol
create_booking ni chaqirgan. Prompt'ga ishonish yetarli emas, shuning uchun to'siq kod darajasida turadi
(LangGraph'da `reject` tuguni). Sof Python: Django va LangChain'ga bog'liq emas, shuning uchun test qilinadi.
"""
import re

GUARDED_TOOLS = {"create_booking", "cancel_booking", "reschedule_booking", "join_queue",
                 "create_recurring_booking", "stop_recurring"}

REJECT_MESSAGE = (
    "TASDIQ YO'Q: mijoz bu amalni hali aniq tasdiqlamagan, shuning uchun bajarilmadi. Hozir tool chaqirma. "
    "Mijozga usta, xizmat, sana, vaqt va narxni qisqa xulosa qilib yoz va 'Tasdiqlaysizmi?' deb so'ra. "
    "Mijoz KEYINGI xabarida 'ha' desa, shundan keyingina chaqir."
)

_AFFIRM = {
    "ha", "xa", "xop", "xo'p", "mayli", "ok", "okay", "oke", "albatta", "tasdiqlayman", "tasdiqlang",
    "tasdiqlash", "to'g'ri", "togri", "ma'qul", "maqul", "yes",
    "да", "ага", "угу", "подтверждаю", "подтверждаем", "подтвердить", "давайте", "хорошо", "согласен",
    "согласна", "верно", "конечно",
}
_NEGATIVE = {"yo'q", "yoq", "emas", "qilmang", "bo'lmasin", "stop", "нет", "не"}
_CHANGE_PREFIXES = ("o'zgart", "ozgart", "boshqa", "lekin", "ammo", "измен", "друг", "поменя", "но")
MAX_WORDS = 14  # uzun xabar oddiy "ha" emas: ichida yangi so'rov bo'lishi mumkin


def _tokens(text: str) -> list[str]:
    t = (text or "").lower()
    for ch in ("’", "ʻ", "ʼ", "‘", "`"):
        t = t.replace(ch, "'")
    return re.findall(r"[\w']+", t)


def is_confirmation(text: str) -> bool:
    """Mijoz xabari aniq tasdiqmi? ('Ha, tasdiqlayman', 'Да, подтверждаю'). Dastlabki so'rov ('yozib qo'ying') emas."""
    tokens = _tokens(text)
    if not tokens or len(tokens) > MAX_WORDS:
        return False
    if any(t in _NEGATIVE for t in tokens):
        return False
    if any(t == p or t.startswith(p) for t in tokens for p in _CHANGE_PREFIXES if len(p) > 2 or t == p):
        return False
    return any(t in _AFFIRM for t in tokens)


def needs_confirmation(tool_calls) -> bool:
    return any((c.get("name") if isinstance(c, dict) else None) in GUARDED_TOOLS for c in tool_calls or [])
