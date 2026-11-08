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
    def find_best_slots(service_id: int, date: str, master_id: int = 0,
                        part_of_day: str = "", preferred_time: str = "") -> str:
        """Mijozning xohishiga eng mos bo'sh vaqtlarni qidiradi (usta aytilmasa hamma ustalar bo'yicha,
        bir necha kun oldinga). 'Ertaga kechqurun', 'ertalab', 'soat 15 atrofida' kabi noaniq so'rovlar
        uchun ishlat. date: boshlanish sanasi YYYY-MM-DD. part_of_day: morning (ertalab),
        afternoon (kunduzi), evening (kechqurun) yoki bo'sh. preferred_time: HH:MM yoki bo'sh.
        Natijadagi sana so'ralgandan farq qilishi mumkin."""
        args = {"service_id": service_id, "date": date}
        if master_id:
            args["master_id"] = master_id
        if part_of_day:
            args["part_of_day"] = part_of_day
        if preferred_time:
            args["preferred_time"] = preferred_time
        return _dump(run_tool("find_best_slots", user, args))

    @tool
    def my_bookings(upcoming_only: bool = True) -> str:
        """Mijozning o'z bronlari (id, usta, xizmat, sana, vaqt, holat). upcoming_only=True: faqat kelgusi faol bronlar.
        Bronni bekor qilishdan oldin id ni olish uchun shuni chaqir."""
        return _dump(run_tool("my_bookings", user, {"upcoming_only": upcoming_only}))

    @tool
    def cancel_booking(booking_id: int) -> str:
        """Mijozning o'z bronini bekor qiladi. FAQAT mijoz qaysi bronni bekor qilishni aniq
        tasdiqlagandan KEYIN chaqir. booking_id ni my_bookings dan ol."""
        return _dump(run_tool("cancel_booking", user, {"booking_id": booking_id}))

    @tool
    def search_shop_info(query: str, shop_id: int = 0) -> str:
        """Qoidalar (bekor qilish, kechikish, to'lov), qulayliklar, usta haqida ma'lumot va mijoz
        sharhlarini qidiradi. shop_id ixtiyoriy (0 = hammasi)."""
        return _dump(
            run_tool("search_shop_info", user, {"query": query, "shop_id": shop_id or None})
        )

    return [
        list_shops, list_services, list_masters, get_available_slots, find_best_slots,
        create_booking, my_bookings, cancel_booking, search_shop_info,
    ]
