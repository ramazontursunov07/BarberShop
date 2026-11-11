// Telegram Mini App yordamchilari. Oddiy brauzerda hammasi bo'sh qiymat qaytaradi.
const tg = window.Telegram?.WebApp ?? null;

export const tgInitData = () => tg?.initData || "";
export const tgLang = () => tg?.initDataUnsafe?.user?.language_code?.slice(0, 2) || null;

export function initTelegram() {
  if (!tg) return;
  tg.ready();
  tg.expand();
}
