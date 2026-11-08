"""LangChain tool'lari. Foydalanuvchi (user) closure orqali bog'lanadi, shuning uchun
LLM boshqa odam nomidan bron qila olmaydi."""
import json

from langchain_core.tools import tool

from .tools import run_tool


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


def make_tools(user):
    @tool
    def list_shops(city: str = "") -> str:
        """Sartaroshxonalar ro'yxati: nomi, manzili, ish vaqti. city ixtiyoriy (bo'sh = hammasi)."""
        return _dump(run_tool("list_shops", user, {"city": city} if city else {}))

    @tool
    def list_services(shop_id: int = 0) -> str:
        """Xizmatlar ro'yxati: nomi, narxi (so'm), davomiyligi (daqiqa). shop_id ixtiyoriy (0 = hammasi)."""
        return _dump(run_tool("list_services", user, {"shop_id": shop_id} if shop_id else {}))

    @tool
    def list_masters(shop_id: int = 0) -> str:
        """Ustalar ro'yxati. shop_id ixtiyoriy (0 = hammasi)."""
        return _dump(run_tool("list_masters", user, {"shop_id": shop_id} if shop_id else {}))

    @tool
    def get_available_slots(master_id: int, service_id: int, date: str) -> str:
        """Usta va xizmat uchun berilgan sanadagi bo'sh boshlanish vaqtlari. date: YYYY-MM-DD.
        Usta va xizmat bir sartaroshxonaga tegishli bo'lishi kerak."""
        return _dump(
            run_tool("get_available_slots", user,
                     {"master_id": master_id, "service_id": service_id, "date": date})
        )

    @tool
    def create_booking(master_id: int, service_id: int, date: str, start_time: str) -> str:
        """Bron yaratadi. FAQAT mijoz usta, xizmat, sana va vaqtni aniq tasdiqlagandan KEYIN chaqir.
        date: YYYY-MM-DD, start_time: HH:MM."""
        return _dump(
            run_tool("create_booking", user,
                     {"master_id": master_id, "service_id": service_id,
                      "date": date, "start_time": start_time})
        )

    @tool
    def search_shop_info(query: str, shop_id: int = 0) -> str:
        """Qoidalar (bekor qilish, kechikish, to'lov), qulayliklar, usta haqida ma'lumot va mijoz
        sharhlarini qidiradi. shop_id ixtiyoriy (0 = hammasi)."""
        return _dump(
            run_tool("search_shop_info", user, {"query": query, "shop_id": shop_id or None})
        )

    return [list_shops, list_services, list_masters, get_available_slots, create_booking, search_shop_info]
