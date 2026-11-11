import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, tokens } from "./api.js";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokens.access));

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
    if (tokens.access) loadMe();
  }, [loadMe]);

  useEffect(() => {
    const onLogout = () => setUser(null);
    window.addEventListener("auth:logout", onLogout);
    return () => window.removeEventListener("auth:logout", onLogout);
  }, []);

  const login = async (phone, password) => {
    const data = await api("/api/users/login/", { method: "POST", body: { phone, password }, auth: false });
    tokens.set(data.access, data.refresh);
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
