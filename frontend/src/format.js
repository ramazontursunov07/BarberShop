const TZ = "Asia/Tashkent";

export const money = (value) => `${Number(value).toLocaleString("ru-RU")} so'm`;

// Bugungi sana sartaroshxona vaqti bilan (YYYY-MM-DD)
export const todayISO = () => new Date().toLocaleDateString("en-CA", { timeZone: TZ });

export const dateTime = (iso) =>
  new Date(iso).toLocaleString("ru-RU", {
    timeZone: TZ,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export const STATUS = {
  pending: "Kutilmoqda",
  confirmed: "Tasdiqlangan",
  completed: "Bajarilgan",
  no_show: "Kelmadi",
  cancelled: "Bekor qilingan",
};
