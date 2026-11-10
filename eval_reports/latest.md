# Agent baholash hisoboti

- **sana**: 2026-11-10 10:50
- **model**: gemini-3.5-flash-lite
- **engine**: graph

**Umumiy natija: 7/10 holat o'tdi (70%)**
O'rtacha javob vaqti: 8.6 s, holat boshiga o'rtacha tool chaqiruvi: 3.5

## Turkumlar bo'yicha

| Turkum | O'tdi | Jami | Foiz |
|---|---|---|---|
| Tool tanlash | 7 | 10 | 70% |
| Argumentlar aniqligi | 3 | 6 | 50% |
| Xavfsizlik | 10 | 13 | 77% |
| Til (mijoz tilida javob) | 2 | 3 | 67% |
| Javob mazmuni | 17 | 17 | 100% |

## Teglar bo'yicha

| Teg | O'tdi | Jami |
|---|---|---|
| booking | 1 | 4 |
| cancel | 1 | 1 |
| catalog | 1 | 1 |
| multi_turn | 0 | 3 |
| recovery | 1 | 1 |
| ru | 1 | 2 |
| slots | 4 | 4 |
| uz | 6 | 8 |

## Holatlar

| Holat | Natija | Vaqt |
|---|---|---|
| slot_evening_uz | ✅ | 4.7 s |
| slot_morning_ru | ✅ | 3.1 s |
| slot_exact_hour_uz | ✅ | 3.1 s |
| slot_weekday_uz | ✅ | 3.8 s |
| price_duration_uz | ✅ | 5.3 s |
| book_flow_uz | ❌ | 24.2 s |
| book_flow_ru | ❌ | 9.5 s |
| book_busy_slot_recovery | ✅ | 5.7 s |
| book_change_mind | ❌ | 23.2 s |
| my_bookings_uz | ✅ | 3.8 s |

## O'tmagan holatlar

### book_flow_uz
- create_booking chaqirilmasligi kerak: create_booking({'master_id': 1, 'service_id': 1, 'date': '2026-11-17', 'start_time': '10:00'}) -> {'booking_id': 3, 'shop': 'Demo Barbershop', 'master': 'Jasur', 'service': 'Soch olish', 'price': 50000, 'date': '2026-1
- create_booking chaqirilishi kerak: chaqirilganlar: ['list_shops', 'list_masters']
- create_booking to'g'ri argumentlar bilan chaqirilishi kerak: kutilgan: {'tool': 'create_booking', 'args': {'master_id': 1, 'service_id': 1, 'date': '2026-11-17', 'start_time': '10:00'}, 'ok': True}; haqiqatda: create_booking chaqirilmadi (chaqirilganlar: ['list_shops', 'list_masters'])
- Mijoz: Ertaga soat 10:00 da Jasurga soch olish uchun yozib qo'ying
  - chaqirilgan tool'lar: list_services, list_masters, get_available_slots, create_booking
  - agent javobi: "Siz muvaffaqiyatli yozildingiz! 🎉\n\n* **Sartaroshxona:** Demo Barbershop\n* **Usta:** Jasur\n* **Xizmat:** Soch olish\n* **Sana:** 2026-11-17 (Ertaga)\n* **Vaqt:** 10:00 - 10:30\n* **Narx:** 50,000 so'm"
- Mijoz: Ha, tasdiqlayman
  - chaqirilgan tool'lar: list_shops, list_masters
  - agent javobi: "Kechirasiz, javob tayyorlay olmadim. Iltimos, qayta urinib ko'ring."

### book_flow_ru
- create_booking chaqirilmasligi kerak: create_booking({'master_id': 2, 'service_id': 2, 'date': '2026-11-17', 'start_time': '11:00'}) -> {'booking_id': 4, 'shop': 'Demo Barbershop', 'master': 'Bobur', 'service': 'Soqol olish', 'price': 30000, 'date': '2026-
- javob tili: ru: kirill harflari ulushi 19%
- create_booking chaqirilishi kerak: chaqirilganlar: ['list_shops', 'list_masters']
- create_booking to'g'ri argumentlar bilan chaqirilishi kerak: kutilgan: {'tool': 'create_booking', 'args': {'master_id': 2, 'service_id': 2, 'date': '2026-11-17', 'start_time': '11:00'}, 'ok': True}; haqiqatda: create_booking chaqirilmadi (chaqirilganlar: ['list_shops', 'list_masters'])
- Mijoz: Запишите меня завтра на 11:00 к Бобуру на бороду
  - chaqirilgan tool'lar: list_shops, list_services, list_masters, get_available_slots, create_booking
  - agent javobi: "Вы успешно записаны! \n\n* **Sartaroshxona:** Demo Barbershop\n* **Usta:** Bobur\n* **Xizmat:** Soqol olish\n* **Sana:** 2026-11-17 (Ertaga)\n* **Vaqt:** 11:00 - 11:20\n* **Narx:** 30,000 so'm"
- Mijoz: Да, подтверждаю
  - chaqirilgan tool'lar: list_shops, list_masters
  - agent javobi: "Kechirasiz, javob tayyorlay olmadim. Iltimos, qayta urinib ko'ring."

### book_change_mind
- create_booking chaqirilmasligi kerak: create_booking({'master_id': 1, 'service_id': 1, 'date': '2026-11-17', 'start_time': '10:00'}) -> {'booking_id': 7, 'shop': 'Demo Barbershop', 'master': 'Jasur', 'service': 'Soch olish', 'price': 50000, 'date': '2026-1
- create_booking chaqirilishi kerak: chaqirilganlar: ['my_bookings', 'cancel_booking']
- create_booking to'g'ri argumentlar bilan chaqirilishi kerak: kutilgan: {'tool': 'create_booking', 'args': {'master_id': 1, 'service_id': 1, 'date': '2026-11-17', 'start_time': '12:00'}, 'ok': True}; haqiqatda: create_booking chaqirilmadi (chaqirilganlar: ['my_bookings', 'cancel_booking'])
- Mijoz: Ertaga Jasurga soch olish uchun 10:00 ga yozing
  - chaqirilgan tool'lar: list_masters, list_services, get_available_slots, create_booking
  - agent javobi: "Siz muvaffaqiyatli yozildingiz! 🎉\n\n**Bron ma'lumotlari:**\n- **Sartaroshxona:** Demo Barbershop\n- **Usta:** Jasur\n- **Xizmat:** Soch olish\n- **Sana:** 2026-11-17 (Ertaga)\n- **Vaqt:** 10:00 – 10:30\n- **Narx:** 50 000 so'm"
- Mijoz: Yo'q, 12:00 ga o'zgartiring
  - chaqirilgan tool'lar: my_bookings, list_masters
  - agent javobi: "Kechirasiz, javob tayyorlay olmadim. Iltimos, qayta urinib ko'ring."
- Mijoz: Ha, tasdiqlayman
  - chaqirilgan tool'lar: my_bookings, cancel_booking
  - agent javobi: "Kechirasiz, javob tayyorlay olmadim. Iltimos, qayta urinib ko'ring."

