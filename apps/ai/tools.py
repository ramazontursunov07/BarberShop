"""Claude'ga beriladigan tool'lar: sxema + bajaruvchi funksiya."""
from . import services

TOOLS = [
    {
        "name": "list_services",
        "description": "Xizmatlar ro'yxati: nomi, narxi va davomiyligi (daqiqada).",
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
        "name": "get_available_slots",
        "description": "Usta va xizmat uchun berilgan sanadagi bo'sh boshlanish vaqtlarini qaytaradi.",
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

_FUNCS = {
    "list_services": services.list_services,
    "list_masters": services.list_masters,
    "get_available_slots": services.get_available_slots,
    "create_booking": services.create_booking,
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
    except Exception as exc:  # ORM DoesNotExist va boshqalar
        return {"error": f"{type(exc).__name__}: {exc}"}
