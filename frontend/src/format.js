const TZ = "Asia/Tashkent";
const LOCALE = { uz: "ru-RU", ru: "ru-RU", en: "en-GB" };

export const money = (value, t) => `${Number(value).toLocaleString("ru-RU")} ${t("currency")}`;

export const percent = (ratio) => `${Math.round(ratio * 1000) / 10}%`;

// Bugungi sana sartaroshxona vaqti bilan (YYYY-MM-DD)
export const todayISO = () => new Date().toLocaleDateString("en-CA", { timeZone: TZ });

export const shiftDate = (iso, days) => {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
};

export const dateTime = (iso, lang) =>
  new Date(iso).toLocaleString(LOCALE[lang] || "ru-RU", {
    timeZone: TZ,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

export const timeOnly = (iso) =>
  new Date(iso).toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
