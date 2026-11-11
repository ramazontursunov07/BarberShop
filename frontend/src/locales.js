// Tarjimalar. Kalit topilmasa o'zbekcha matn ko'rsatiladi.
const uz = {
  "nav.shops": "Sartaroshxonalar", "nav.bookings": "Bronlarim", "nav.panel": "Panel",
  "nav.login": "Kirish", "nav.logout": "Chiqish",
  loading: "Yuklanmoqda...", wait: "Kuting...", back: "← Orqaga", currency: "so'm", minutes: "daqiqa",

  "login.title": "Kirish", "register.title": "Ro'yxatdan o'tish", phone: "Telefon raqam",
  first_name: "Ism", last_name: "Familiya", password: "Parol",
  "login.submit": "Kirish", "register.submit": "Ro'yxatdan o'tish",
  "login.to_register": "Akkauntingiz yo'qmi? Ro'yxatdan o'ting", "login.to_login": "Akkauntingiz bormi? Kiring",
  "login.bad": "Telefon raqam yoki parol noto'g'ri",

  "shops.title": "Sartaroshxonalar", "shops.search": "Nomi yoki manzil bo'yicha qidirish", "shops.empty": "Hech narsa topilmadi.",

  "shop.not_found": "Sartaroshxona topilmadi", "shop.step1": "1. Xizmatni tanlang", "shop.step2": "2. Ustani tanlang",
  "shop.step3": "3. Sana va vaqt", "shop.no_services": "Xizmatlar hali qo'shilmagan.", "shop.no_masters": "Ustalar hali qo'shilmagan.",
  "shop.not_rated": "Hali baholanmagan", "shop.login_needed": "Bo'sh vaqtlarni ko'rish va bron qilish uchun", "shop.login_link": "kiring",
  "shop.pick_first": "Avval xizmat va ustani tanlang.", "shop.searching": "Bo'sh vaqtlar qidirilmoqda...",
  "shop.no_slots": "Bu kunga bo'sh vaqt yo'q. Boshqa sana yoki ustani tanlang.", "shop.price": "Narxi", "shop.book": "Bron qilish",
  "shop.waitlist": "Kutish ro'yxatiga yozilish", "shop.waitlist_done": "Kutish ro'yxatidasiz. Vaqt bo'shasa Telegram orqali xabar beramiz.",
  "shop.reviews": "Sharhlar", "shop.no_reviews": "Hali sharhlar yo'q.", "shop.faq": "Ko'p so'raladigan savollar",

  "bk.title": "Bronlarim", "bk.upcoming": "Kelgusi bronlar", "bk.history": "Tarix", "bk.empty": "Hali bronlaringiz yo'q.",
  "bk.master": "usta", "bk.cancel": "Bekor qilish", "bk.cancel_confirm": "Bronni bekor qilasizmi?",
  "bk.reschedule": "Ko'chirish", "bk.reschedule_title": "Boshqa vaqtga ko'chirish", "bk.confirm_move": "Ko'chirish",
  "bk.close": "Yopish", "bk.review": "Sharh yozish", "bk.review_title": "Sharh va baho", "bk.comment": "Fikringiz (ixtiyoriy)",
  "bk.send": "Yuborish", "bk.reviewed": "Sharh yozilgan ✓", "bk.waitlist": "Kutish ro'yxatim", "bk.leave": "Chiqish",

  "status.pending": "Kutilmoqda", "status.confirmed": "Tasdiqlangan", "status.completed": "Bajarilgan",
  "status.no_show": "Kelmadi", "status.cancelled": "Bekor qilingan",

  "own.title": "Boshqaruv paneli", "own.tab_today": "Bronlar", "own.tab_stats": "Statistika", "own.tab_clients": "Mijozlar",
  "own.no_shops": "Sartaroshxonangiz yo'q. Avval Django admin yoki API orqali yarating.", "own.no_bookings": "Bu kunga bronlar yo'q.",
  "own.total": "Jami", "own.last_days": "Oxirgi {n} kun",
  "own.act.confirmed": "Tasdiqlash", "own.act.completed": "Bajarildi", "own.act.no_show": "Kelmadi", "own.act.cancelled": "Bekor qilish",

  "st.revenue": "Daromad", "st.completed": "Bajarilgan", "st.avg": "O'rtacha chek", "st.no_show": "Kelmadi", "st.cancel": "Bekor qilingan",
  "st.top": "Eng ko'p so'ralgan xizmatlar", "st.hours": "Eng band soatlar", "st.days": "Eng band kunlar", "st.masters": "Ustalar",
  "st.bookings": "bron", "st.empty": "Ma'lumot yo'q",

  "cl.search": "Ism yoki telefon", "cl.sort_last": "Oxirgi tashrif", "cl.sort_visits": "Tashriflar soni",
  "cl.sort_spent": "Sarflagan summa", "cl.sort_no_shows": "Kelmaganlar", "cl.visits": "tashrif", "cl.spent": "Sarflagan",
  "cl.no_shows": "Kelmadi", "cl.cancelled": "Bekor", "cl.last": "Oxirgi tashrif", "cl.fav_master": "Afzal usta",
  "cl.fav_service": "Afzal xizmat", "cl.history": "Tarix", "cl.empty": "Mijozlar topilmadi.",

  "wd.Dushanba": "Dushanba", "wd.Seshanba": "Seshanba", "wd.Chorshanba": "Chorshanba", "wd.Payshanba": "Payshanba",
  "wd.Juma": "Juma", "wd.Shanba": "Shanba", "wd.Yakshanba": "Yakshanba",
};

const ru = {
  "nav.shops": "Барбершопы", "nav.bookings": "Мои записи", "nav.panel": "Панель", "nav.login": "Войти", "nav.logout": "Выйти",
  loading: "Загрузка...", wait: "Подождите...", back: "← Назад", currency: "сум", minutes: "мин",

  "login.title": "Вход", "register.title": "Регистрация", phone: "Номер телефона", first_name: "Имя", last_name: "Фамилия", password: "Пароль",
  "login.submit": "Войти", "register.submit": "Зарегистрироваться",
  "login.to_register": "Нет аккаунта? Зарегистрируйтесь", "login.to_login": "Уже есть аккаунт? Войдите",
  "login.bad": "Неверный номер телефона или пароль",

  "shops.title": "Барбершопы", "shops.search": "Поиск по названию или адресу", "shops.empty": "Ничего не найдено.",

  "shop.not_found": "Барбершоп не найден", "shop.step1": "1. Выберите услугу", "shop.step2": "2. Выберите мастера",
  "shop.step3": "3. Дата и время", "shop.no_services": "Услуги ещё не добавлены.", "shop.no_masters": "Мастера ещё не добавлены.",
  "shop.not_rated": "Пока без оценок", "shop.login_needed": "Чтобы увидеть свободное время и записаться,", "shop.login_link": "войдите",
  "shop.pick_first": "Сначала выберите услугу и мастера.", "shop.searching": "Ищем свободное время...",
  "shop.no_slots": "На этот день нет свободного времени. Выберите другую дату или мастера.", "shop.price": "Цена", "shop.book": "Записаться",
  "shop.waitlist": "Встать в лист ожидания", "shop.waitlist_done": "Вы в листе ожидания. Если время освободится, сообщим в Telegram.",
  "shop.reviews": "Отзывы", "shop.no_reviews": "Отзывов пока нет.", "shop.faq": "Частые вопросы",

  "bk.title": "Мои записи", "bk.upcoming": "Предстоящие", "bk.history": "История", "bk.empty": "У вас пока нет записей.",
  "bk.master": "мастер", "bk.cancel": "Отменить", "bk.cancel_confirm": "Отменить запись?",
  "bk.reschedule": "Перенести", "bk.reschedule_title": "Перенос на другое время", "bk.confirm_move": "Перенести",
  "bk.close": "Закрыть", "bk.review": "Оставить отзыв", "bk.review_title": "Отзыв и оценка", "bk.comment": "Ваш отзыв (необязательно)",
  "bk.send": "Отправить", "bk.reviewed": "Отзыв оставлен ✓", "bk.waitlist": "Мой лист ожидания", "bk.leave": "Выйти",

  "status.pending": "Ожидает", "status.confirmed": "Подтверждена", "status.completed": "Выполнена",
  "status.no_show": "Не пришёл", "status.cancelled": "Отменена",

  "own.title": "Панель управления", "own.tab_today": "Записи", "own.tab_stats": "Статистика", "own.tab_clients": "Клиенты",
  "own.no_shops": "У вас нет барбершопа. Сначала создайте его через Django admin или API.", "own.no_bookings": "На этот день записей нет.",
  "own.total": "Всего", "own.last_days": "Последние {n} дн.",
  "own.act.confirmed": "Подтвердить", "own.act.completed": "Выполнено", "own.act.no_show": "Не пришёл", "own.act.cancelled": "Отменить",

  "st.revenue": "Выручка", "st.completed": "Выполнено", "st.avg": "Средний чек", "st.no_show": "Не пришли", "st.cancel": "Отменены",
  "st.top": "Самые популярные услуги", "st.hours": "Самые загруженные часы", "st.days": "Самые загруженные дни", "st.masters": "Мастера",
  "st.bookings": "зап.", "st.empty": "Нет данных",

  "cl.search": "Имя или телефон", "cl.sort_last": "Последний визит", "cl.sort_visits": "Число визитов",
  "cl.sort_spent": "Потрачено", "cl.sort_no_shows": "Неявки", "cl.visits": "визитов", "cl.spent": "Потрачено",
  "cl.no_shows": "Неявки", "cl.cancelled": "Отмены", "cl.last": "Последний визит", "cl.fav_master": "Любимый мастер",
  "cl.fav_service": "Любимая услуга", "cl.history": "История", "cl.empty": "Клиенты не найдены.",

  "wd.Dushanba": "Понедельник", "wd.Seshanba": "Вторник", "wd.Chorshanba": "Среда", "wd.Payshanba": "Четверг",
  "wd.Juma": "Пятница", "wd.Shanba": "Суббота", "wd.Yakshanba": "Воскресенье",
};

const en = {
  "nav.shops": "Barbershops", "nav.bookings": "My bookings", "nav.panel": "Dashboard", "nav.login": "Log in", "nav.logout": "Log out",
  loading: "Loading...", wait: "Please wait...", back: "← Back", currency: "UZS", minutes: "min",

  "login.title": "Log in", "register.title": "Sign up", phone: "Phone number", first_name: "First name", last_name: "Last name", password: "Password",
  "login.submit": "Log in", "register.submit": "Sign up",
  "login.to_register": "No account? Sign up", "login.to_login": "Already have an account? Log in",
  "login.bad": "Wrong phone number or password",

  "shops.title": "Barbershops", "shops.search": "Search by name or address", "shops.empty": "Nothing found.",

  "shop.not_found": "Barbershop not found", "shop.step1": "1. Choose a service", "shop.step2": "2. Choose a barber",
  "shop.step3": "3. Date and time", "shop.no_services": "No services yet.", "shop.no_masters": "No barbers yet.",
  "shop.not_rated": "Not rated yet", "shop.login_needed": "To see free times and book,", "shop.login_link": "log in",
  "shop.pick_first": "Choose a service and a barber first.", "shop.searching": "Looking for free times...",
  "shop.no_slots": "No free times that day. Try another date or barber.", "shop.price": "Price", "shop.book": "Book",
  "shop.waitlist": "Join the waitlist", "shop.waitlist_done": "You're on the waitlist. We'll message you on Telegram if a slot opens.",
  "shop.reviews": "Reviews", "shop.no_reviews": "No reviews yet.", "shop.faq": "FAQ",

  "bk.title": "My bookings", "bk.upcoming": "Upcoming", "bk.history": "History", "bk.empty": "You have no bookings yet.",
  "bk.master": "barber", "bk.cancel": "Cancel", "bk.cancel_confirm": "Cancel this booking?",
  "bk.reschedule": "Reschedule", "bk.reschedule_title": "Move to another time", "bk.confirm_move": "Move",
  "bk.close": "Close", "bk.review": "Write a review", "bk.review_title": "Review and rating", "bk.comment": "Your comment (optional)",
  "bk.send": "Send", "bk.reviewed": "Reviewed ✓", "bk.waitlist": "My waitlist", "bk.leave": "Leave",

  "status.pending": "Pending", "status.confirmed": "Confirmed", "status.completed": "Completed",
  "status.no_show": "No-show", "status.cancelled": "Cancelled",

  "own.title": "Dashboard", "own.tab_today": "Bookings", "own.tab_stats": "Statistics", "own.tab_clients": "Clients",
  "own.no_shops": "You have no barbershop yet. Create one via Django admin or the API first.", "own.no_bookings": "No bookings for this day.",
  "own.total": "Total", "own.last_days": "Last {n} days",
  "own.act.confirmed": "Confirm", "own.act.completed": "Done", "own.act.no_show": "No-show", "own.act.cancelled": "Cancel",

  "st.revenue": "Revenue", "st.completed": "Completed", "st.avg": "Average check", "st.no_show": "No-shows", "st.cancel": "Cancelled",
  "st.top": "Most requested services", "st.hours": "Busiest hours", "st.days": "Busiest days", "st.masters": "Barbers",
  "st.bookings": "bookings", "st.empty": "No data",

  "cl.search": "Name or phone", "cl.sort_last": "Last visit", "cl.sort_visits": "Number of visits",
  "cl.sort_spent": "Amount spent", "cl.sort_no_shows": "No-shows", "cl.visits": "visits", "cl.spent": "Spent",
  "cl.no_shows": "No-shows", "cl.cancelled": "Cancelled", "cl.last": "Last visit", "cl.fav_master": "Favorite barber",
  "cl.fav_service": "Favorite service", "cl.history": "History", "cl.empty": "No clients found.",

  "wd.Dushanba": "Monday", "wd.Seshanba": "Tuesday", "wd.Chorshanba": "Wednesday", "wd.Payshanba": "Thursday",
  "wd.Juma": "Friday", "wd.Shanba": "Saturday", "wd.Yakshanba": "Sunday",
};

export const LANGS = { uz, ru, en };
export const LANG_LIST = ["uz", "ru", "en"];
