# Agent baholash hisoboti

- **sana**: 2026-11-10 22:15
- **model**: gemini-3.5-flash-lite
- **engine**: graph

**Umumiy natija: 7/10 holat o'tdi (70%)**
O'rtacha javob vaqti: 11.6 s, holat boshiga o'rtacha tool chaqiruvi: 3.6

## Turkumlar bo'yicha

| Turkum | O'tdi | Jami | Foiz |
|---|---|---|---|
| Tool tanlash | 7 | 9 | 78% |
| Argumentlar aniqligi | 3 | 5 | 60% |
| Xavfsizlik | 12 | 12 | 100% |
| Til (mijoz tilida javob) | 2 | 3 | 67% |
| Javob mazmuni | 16 | 16 | 100% |

## Teglar bo'yicha

| Teg | O'tdi | Jami |
|---|---|---|
| booking | 3 | 4 |
| cancel | 1 | 1 |
| catalog | 1 | 1 |
| multi_turn | 2 | 3 |
| recovery | 1 | 1 |
| ru | 0 | 2 |
| slots | 2 | 4 |
| uz | 7 | 8 |

## Holatlar

| Holat | Natija | Vaqt |
|---|---|---|
| slot_evening_uz | ✅ | 18.1 s |
| slot_morning_ru | ❌ | 5.6 s |
| slot_exact_hour_uz | ❌ | 11.6 s |
| slot_weekday_uz | ✅ | 4.2 s |
| price_duration_uz | ✅ | 3.6 s |
| book_flow_uz | ✅ | 24.0 s |
| book_flow_ru | ⚠️ xato | 7.5 s |
| book_busy_slot_recovery | ✅ | 7.1 s |
| book_change_mind | ✅ | 30.8 s |
| my_bookings_uz | ✅ | 3.3 s |

## O'tmagan holatlar

### slot_morning_ru
- find_best_slots chaqirilishi kerak: chaqirilganlar: ['list_shops', 'list_services']
- find_best_slots to'g'ri argumentlar bilan chaqirilishi kerak: kutilgan: {'tool': 'find_best_slots', 'args': {'service_id': 1, 'part_of_day': 'morning', 'date': '2026-11-17'}}; haqiqatda: find_best_slots chaqirilmadi (chaqirilganlar: ['list_shops', 'list_services'])
- javob tili: ru: kirill harflari ulushi 0%
- Mijoz: Мне нужно подстричься завтра утром
  - chaqirilgan tool'lar: list_shops, list_services
  - agent javobi: "Kechirasiz, javob tayyorlay olmadim. Iltimos, qayta urinib ko'ring."

### slot_exact_hour_uz
- find_best_slots chaqirilishi kerak: chaqirilganlar: ['list_services']
- find_best_slots to'g'ri argumentlar bilan chaqirilishi kerak: kutilgan: {'tool': 'find_best_slots', 'args': {'service_id': 2, 'preferred_time': '15:00', 'date': '2026-11-17'}}; haqiqatda: find_best_slots chaqirilmadi (chaqirilganlar: ['list_services'])
- Mijoz: Ertaga soat 15:00 atrofida soqol olmoqchiman
  - chaqirilgan tool'lar: list_services
  - agent javobi: "Kechirasiz, javob tayyorlay olmadim. Iltimos, qayta urinib ko'ring."

### book_flow_ru
- XATO: GraphRecursionError: Recursion limit of 12 reached without hitting a stop condition. You can increase the limit by setting the `recursion_limit` config key. For troubleshooting, visit: https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT
- Mijoz: Запишите меня завтра на 11:00 к Бобуру на бороду
  - chaqirilgan tool'lar: list_shops, list_masters, list_services, get_available_slots
  - agent javobi: 'Мастер: Бобур  \nУслуга: Соqol olish (Соqol)  \nДата: 17.11.2026 (завтра)  \nВремя: 11:00  \nСтоимость: 30 000 сум  \n\nПодтверждаете запись?'
- Mijoz: Да, подтверждаю
  - chaqirilgan tool'lar: list_shops, list_services, list_masters, get_available_slots, create_booking
  - agent javobi: ''

