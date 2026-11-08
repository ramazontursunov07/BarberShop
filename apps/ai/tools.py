"""LLM'ga beriladigan tool'lar: sxema + bajaruvchi funksiya."""
from . import services

TOOLS = [
    {
        "name": "list_shops",
        "description": "Sartaroshxonalar ro'yxati: nomi, manzili, ish vaqti. Shahar bo'yicha filtrlash mumkin.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "Ixtiyoriy: shahar nomi"}},
        },
    },
    {
        "name": "list_services",
        "description": "Xizmatlar ro'yxati: nomi, narxi (so'm) va davomiyligi (daqiqada).",
        "input_schema": {
            "type": "object",
            "properties": {"shop_id": {"type": "integer", "description": "Ixtiyoriy: sartaroshxona ID"}},
        },
    },
    {
        "name": "list_masters",
        "description": "Ustalar ro'yxati.",
        "input_schema": {
            "type": "object",
            "properties": {"shop_id": {"type": "integer", "description": "Ixtiyoriy: sartaroshxona ID"}},
        },
    },
    {
        "name": "search_shop_info",
        "description": (
            "Sartaroshxona qoidalari (bekor qilish, kechikish, to'lov), qulayliklar, aksiyalar, "
            "usta haqida ma'lumot va mijoz sharhlarini qidiradi. Faqat shu tool natijasiga tayanib javob ber. "
            "Narx va davomiylik uchun list_services ni ishlat."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Mijoz savoli yoki qidiruv iborasi"},
                "shop_id": {"type": "integer", "description": "Ixtiyoriy: sartaroshxona ID (list_shops dan)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_available_slots",
        "description": (
            "Usta va xizmat uchun berilgan sanadagi bo'sh boshlanish vaqtlarini qaytaradi. "
            "Xizmat va usta bir sartaroshxonaga tegishli bo'lishi kerak."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "master_id": {"type": "integer"},
                "service_id": {"type": "integer"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["master_id", "service_id", "date"],
        },
    },
    {
        "name": "find_best_slots",
        "description": (
            "Mijozning xohishiga eng mos bo'sh vaqtlarni qidiradi: usta aytilmasa hamma ustalar bo'yicha, "
            "bir necha kun oldinga. 'Ertaga kechqurun', 'ertalab', 'soat 15 atrofida' kabi noaniq "
            "so'rovlar uchun shuni ishlat. Natijadagi sana so'ralgandan farq qilishi mumkin."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "service_id": {"type": "integer"},
                "date": {"type": "string", "description": "Qidirish boshlanadigan sana, YYYY-MM-DD"},
                "master_id": {"type": "integer", "description": "Ixtiyoriy: aniq usta (0 = hammasi)"},
                "part_of_day": {
                    "type": "string",
                    "enum": ["morning", "afternoon", "evening"],
                    "description": "ertalab=morning, kunduzi/tushdan keyin=afternoon, kechqurun=evening",
                },
                "preferred_time": {"type": "string", "description": "Ixtiyoriy: istalgan vaqt, HH:MM"},
            },
            "required": ["service_id", "date"],
        },
    },
    {
        "name": "my_bookings",
        "description": (
            "Mijozning o'z bronlari ro'yxati (id, usta, xizmat, sana, vaqt, holat). "
            "Bronni bekor qilishdan oldin id ni olish uchun ham shuni chaqir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "upcoming_only": {
                    "type": "boolean",
                    "description": "true = faqat kelgusi faol bronlar (standart), false = hammasi",
                },
            },
        },
    },
    {
        "name": "cancel_booking",
        "description": (
            "Mijozning o'z bronini bekor qiladi. Faqat mijoz qaysi bronni bekor qilishni "
            "aniq tasdiqlagandan KEYIN chaqir. booking_id ni my_bookings dan ol."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"booking_id": {"type": "integer"}},
            "required": ["booking_id"],
        },
    },
    {
        "name": "create_booking",
        "description": (
            "Bron yaratadi. Faqat mijoz usta, xizmat, sana va vaqtni aniq tasdiqlagandan KEYIN chaqir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "master_id": {"type": "integer"},
                "service_id": {"type": "integer"},
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "start_time": {"type": "string", "description": "HH:MM"},
            },
            "required": ["master_id", "service_id", "date", "start_time"],
        },
    },
]


def _search_shop_info(user, query: str, shop_id: int | None = None) -> dict:
    from . import rag  # lazy import: chromadb faqat kerak bo'lganda yuklanadi

    return rag.search_shop_info(query=query, shop_id=shop_id)


_FUNCS = {
    "list_shops": services.list_shops,
    "list_services": services.list_services,
    "list_masters": services.list_masters,
    "get_available_slots": services.get_available_slots,
    "create_booking": services.create_booking,
    "find_best_slots": services.find_best_slots,
    "my_bookings": services.my_bookings,
    "cancel_booking": services.cancel_booking,
    "search_shop_info": _search_shop_info,
}


def run_tool(name: str, user, arguments: dict) -> dict:
    """Tool'ni xavfsiz bajaradi; xatolarni modelga o'qiladigan ko'rinishda qaytaradi."""
    func = _FUNCS.get(name)
    if func is None:
        return {"error": f"Noma'lum tool: {name}"}
    try:
        return func(user, **arguments)
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # DoesNotExist, noto'g'ri argumentlar va h.k.
        return {"error": f"{type(exc).__name__}: {exc}"}
