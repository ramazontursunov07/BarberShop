import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";

export default function Login() {
  const { user, login, register } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const location = useLocation();
  const redirectTo = location.state?.from || "/";

  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ phone: "+998", first_name: "", last_name: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={redirectTo} replace />;

  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (mode === "login") await login(form.phone, form.password);
      else await register(form);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.status === 401 ? t("login.bad") : err.message);
    } finally {
      setBusy(false);
    }
  };

  const isLogin = mode === "login";

  return (
    <form className="card form" onSubmit={submit}>
      <h2>{isLogin ? t("login.title") : t("register.title")}</h2>

      <label>
        {t("phone")}
        <input value={form.phone} onChange={set("phone")} placeholder="+998901234567" inputMode="tel" required />
      </label>

      {!isLogin && (
        <>
          <label>
            {t("first_name")}
            <input value={form.first_name} onChange={set("first_name")} maxLength={20} required />
          </label>
          <label>
            {t("last_name")}
            <input value={form.last_name} onChange={set("last_name")} maxLength={20} />
          </label>
        </>
      )}

      <label>
        {t("password")}
        <input type="password" value={form.password} onChange={set("password")} minLength={isLogin ? 1 : 8} required />
      </label>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={busy}>
        {busy ? t("wait") : isLogin ? t("login.submit") : t("register.submit")}
      </button>

      <button
        type="button"
        className="link"
        onClick={() => {
          setMode(isLogin ? "register" : "login");
          setError("");
        }}
      >
        {isLogin ? t("login.to_register") : t("login.to_login")}
      </button>
    </form>
  );
}
