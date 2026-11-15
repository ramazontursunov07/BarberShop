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

// Hozir sartaroshxona vaqti bilan "HH:MM"
export const nowHM = () => new Date().toLocaleTimeString("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });

// Ish vaqti ichidami? (opens/closes: "HH:MM" yoki "HH:MM:SS")
export const isOpenNow = (opens, closes) => {
  if (!opens || !closes) return null;
  const now = nowHM();
  const o = opens.slice(0, 5);
  const c = closes.slice(0, 5);
  return o <= c ? now >= o && now < c : now >= o || now < c;
};

// Sana tugmalari uchun: { iso, dow: "Dush", day: "15" }
export const dayChip = (iso, lang) => {
  const d = new Date(`${iso}T12:00:00Z`);
  return {
    iso,
    dow: d.toLocaleDateString(LOCALE[lang] || "ru-RU", { weekday: "short", timeZone: "UTC" }).replace(".", ""),
    day: d.getUTCDate(),
  };
};

// Vaqt bo'laklari: ertalab / kunduz / kechqurun
export const partOfDay = (hhmm) => {
  const h = Number(hhmm.slice(0, 2));
  return h < 12 ? "morning" : h < 17 ? "day" : "evening";
};

export const mapsLink = (lat, lng, q) =>
  lat != null && lng != null
    ? `https://www.google.com/maps/search/?api=1&query=${lat},${lng}`
    : `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q || "")}`;
