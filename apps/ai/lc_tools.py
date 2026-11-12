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
    def get_available_slots(master_id: int, service_id: int, date: str,
                            extra_service_ids: list[int] | None = None) -> str:
        """Usta va xizmat uchun berilgan sanadagi bo'sh boshlanish vaqtlari. date: YYYY-MM-DD.
        Usta va xizmat bir sartaroshxonaga tegishli bo'lishi kerak. extra_service_ids: qo'shimcha xizmatlar."""
        args = {"master_id": master_id, "service_id": service_id, "date": date}
        if extra_service_ids:
            args["extra_service_ids"] = extra_service_ids
        return _dump(run_tool("get_available_slots", user, args))

    @tool
    def create_booking(master_id: int, service_id: int, date: str, start_time: str,
                       promo_code: str = "", certificate_code: str = "",
                       extra_service_ids: list[int] | None = None) -> str:
        """Bron yaratadi. FAQAT mijoz usta, xizmat, sana va vaqtni aniq tasdiqlagandan KEYIN chaqir.
        date: YYYY-MM-DD, start_time: HH:MM. promo_code va certificate_code FAQAT mijoz o'zi aytgan bo'lsa
        yuboriladi (kodni o'ylab topma). Sodiqlik chegirmasi avtomatik qo'llanadi; natijadagi price yakuniy narx.
        extra_service_ids: shu tashrifdagi qo'shimcha xizmatlar (soch + soqol)."""
        args = {"master_id": master_id, "service_id": service_id, "date": date, "start_time": start_time}
        if promo_code:
            args["promo_code"] = promo_code
        if certificate_code:
            args["certificate_code"] = certificate_code
        if extra_service_ids:
            args["extra_service_ids"] = extra_service_ids
        return _dump(run_tool("create_booking", user, args))

    @tool
    def find_best_slots(service_id: int, date: str, master_id: int = 0,
                        part_of_day: str = "", preferred_time: str = "",
                        extra_service_ids: list[int] | None = None) -> str:
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
        if extra_service_ids:
            args["extra_service_ids"] = extra_service_ids
        return _dump(run_tool("find_best_slots", user, args))

    @tool
    def my_bookings(upcoming_only: bool = True) -> str:
        """Mijozning o'z bronlari (id, usta, xizmat, sana, vaqt, holat). upcoming_only=True: faqat kelgusi faol bronlar.
        Bronni bekor qilishdan oldin id ni olish uchun shuni chaqir."""
        return _dump(run_tool("my_bookings", user, {"upcoming_only": upcoming_only}))

    @tool
    def my_recommendations() -> str:
        """Mijoz tarixiga qarab tavsiya: oxirgi xizmat va usta, sevimli usta. Mijoz 'odatdagidek' yoki
        'yana o'sha ustaga' desa chaqir; natijadagi usta/xizmatni taklif qil, vaqtni baribir tekshir."""
        return _dump(run_tool("my_recommendations", user, {}))

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

    @tool
    def reschedule_booking(booking_id: int, date: str, start_time: str, master_id: int = 0) -> str:
        """Bronni boshqa vaqtga ko'chiradi. booking_id ni my_bookings dan ol, yangi vaqtni tekshir,
        mijoz tasdiqlagandan KEYIN chaqir. date: YYYY-MM-DD, start_time: HH:MM, master_id ixtiyoriy (0 = o'sha usta)."""
        args = {"booking_id": booking_id, "date": date, "start_time": start_time}
        if master_id:
            args["master_id"] = master_id
        return _dump(run_tool("reschedule_booking", user, args))

    @tool
    def join_waitlist(service_id: int, date: str, master_id: int = 0, from_time: str = "", to_time: str = "") -> str:
        """Bo'sh vaqt yo'q bo'lsa, mijozni kutish ro'yxatiga yozadi (bo'shaganda Telegram xabar boradi).
        from_time/to_time (HH:MM) ixtiyoriy oraliq."""
        args = {"service_id": service_id, "date": date}
        if master_id:
            args["master_id"] = master_id
        if from_time:
            args["from_time"] = from_time
        if to_time:
            args["to_time"] = to_time
        return _dump(run_tool("join_waitlist", user, args))

    @tool
    def quote_price(service_id: int, date: str, start_time: str, promo_code: str = "",
                    certificate_code: str = "", extra_service_ids: list[int] | None = None) -> str:
        """Bron qilmasdan yakuniy narxni hisoblaydi (chegirma, mijoz aytgan promokod/sertifikat, qo'shimcha xizmatlar)."""
        args = {"service_id": service_id, "date": date, "start_time": start_time}
        if promo_code:
            args["promo_code"] = promo_code
        if certificate_code:
            args["certificate_code"] = certificate_code
        if extra_service_ids:
            args["extra_service_ids"] = extra_service_ids
        return _dump(run_tool("quote_price", user, args))

    @tool
    def join_queue(shop_id: int, service_id: int, master_id: int = 0) -> str:
        """'Hoziroq kelaman' deydigan mijozni jonli navbatga qo'yadi, kutish vaqtini qaytaradi. Faqat tasdiqdan KEYIN."""
        args = {"shop_id": shop_id, "service_id": service_id}
        if master_id:
            args["master_id"] = master_id
        return _dump(run_tool("join_queue", user, args))

    @tool
    def queue_status() -> str:
        """Mijozning jonli navbatdagi o'rni va taxminiy kutish vaqti."""
        return _dump(run_tool("queue_status", user, {}))

    @tool
    def leave_queue() -> str:
        """Mijozni jonli navbatdan chiqaradi."""
        return _dump(run_tool("leave_queue", user, {}))

    @tool
    def create_recurring_booking(master_id: int, service_id: int, date: str, start_time: str,
                                 every_weeks: int = 2, end_date: str = "") -> str:
        """Doimiy bron (har N haftada shu usta, shu hafta kuni va soat). Birinchi uchrashuv darhol bron qilinadi.
        Faqat mijoz tasdiqlagandan KEYIN. date: birinchi sana YYYY-MM-DD, start_time: HH:MM."""
        args = {"master_id": master_id, "service_id": service_id, "date": date, "start_time": start_time,
                "every_weeks": every_weeks}
        if end_date:
            args["end_date"] = end_date
        return _dump(run_tool("create_recurring_booking", user, args))

    @tool
    def my_recurring() -> str:
        """Mijozning doimiy bronlari (id bilan)."""
        return _dump(run_tool("my_recurring", user, {}))

    @tool
    def stop_recurring(recurring_id: int) -> str:
        """Doimiy bronni to'xtatadi. id ni my_recurring dan ol; faqat tasdiqdan KEYIN."""
        return _dump(run_tool("stop_recurring", user, {"recurring_id": recurring_id}))

    return [
        list_shops, list_services, list_masters, get_available_slots, find_best_slots,
        create_booking, my_bookings, my_recommendations, cancel_booking, search_shop_info,
        reschedule_booking, join_waitlist, quote_price, join_queue, queue_status, leave_queue,
        create_recurring_booking, my_recurring, stop_recurring,
    ]
