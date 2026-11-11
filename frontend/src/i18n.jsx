import { createContext, useCallback, useContext, useMemo, useState } from "react";
import { LANGS, LANG_LIST } from "./locales.js";
import { tgLang } from "./telegram.js";

const I18nContext = createContext(null);
export const useI18n = () => useContext(I18nContext);

function initialLang() {
  const saved = localStorage.getItem("lang");
  if (LANG_LIST.includes(saved)) return saved;
  const guess = tgLang() || navigator.language?.slice(0, 2);
  return LANG_LIST.includes(guess) ? guess : "uz";
}

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(initialLang);

  const setLang = useCallback((value) => {
    localStorage.setItem("lang", value);
    document.documentElement.lang = value;
    setLangState(value);
  }, []);

  const t = useCallback(
    (key, vars) => {
      let text = LANGS[lang][key] ?? LANGS.uz[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) text = text.replace(`{${k}}`, v);
      return text;
    },
    [lang]
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
