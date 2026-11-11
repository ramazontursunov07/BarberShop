import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, tokens } from "./api.js";
import { tgInitData } from "./telegram.js";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try {
      setUser(await api("/api/users/me/"));
    } catch {
      tokens.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      if (tokens.access) return loadMe();
      // Telegram Mini App ichida bo'lsak va Telegram bog'langan bo'lsa, o'zi kiradi
      if (tgInitData()) {
        try {
          const data = await api("/api/users/telegram/webapp/", {
            method: "POST",
            body: { init_data: tgInitData() },
            auth: false,
          });
          tokens.set(data.access, data.refresh);
          return loadMe();
        } catch {
          /* bog'lanmagan: oddiy kirish oynasi ko'rsatiladi */
        }
      }
      setLoading(false);
    })();
  }, [loadMe]);

  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("auth:logout", onLogout);
    return () => window.removeEventListener("auth:logout", onLogout);
  }, []);

  // Mini App ichida kirgach Telegram akkauntni bog'laymiz: keyingi safar avtomatik kiradi
  const linkTelegram = async () => {
    if (!tgInitData()) return;
    try {
      await api("/api/users/telegram/link/", { method: "POST", body: { init_data: tgInitData() } });
    } catch {
      /* bog'lash muvaffaqiyatsiz bo'lsa ham kirish davom etadi */
    }
  };

  const login = async (phone, password) => {
    const data = await api("/api/users/login/", { method: "POST", body: { phone, password }, auth: false });
    tokens.set(data.access, data.refresh);
    await linkTelegram();
    await loadMe();
  };

  const register = async (form) => {
    await api("/api/users/register/", { method: "POST", body: form, auth: false });
    await login(form.phone, form.password);
  };

  const logout = () => {
    tokens.clear();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>{children}</AuthContext.Provider>
  );
}
