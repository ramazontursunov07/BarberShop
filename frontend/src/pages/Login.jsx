import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { user, login, register } = useAuth();
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
      setError(err.status === 401 ? "Telefon raqam yoki parol noto'g'ri" : err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card form" onSubmit={submit}>
      <h2>{mode === "login" ? "Kirish" : "Ro'yxatdan o'tish"}</h2>

      <label>
        Telefon raqam
        <input value={form.phone} onChange={set("phone")} placeholder="+998901234567" inputMode="tel" required />
      </label>

      {mode === "register" && (
        <>
          <label>
            Ism
            <input value={form.first_name} onChange={set("first_name")} maxLength={20} required />
          </label>
          <label>
            Familiya
            <input value={form.last_name} onChange={set("last_name")} maxLength={20} />
          </label>
        </>
      )}

      <label>
        Parol
        <input type="password" value={form.password} onChange={set("password")} minLength={mode === "register" ? 8 : 1} required />
      </label>

      {error && <p className="error">{error}</p>}

      <button className="btn" disabled={busy}>
        {busy ? "Kuting..." : mode === "login" ? "Kirish" : "Ro'yxatdan o'tish"}
      </button>

      <button type="button" className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>
        {mode === "login" ? "Akkauntingiz yo'qmi? Ro'yxatdan o'ting" : "Akkauntingiz bormi? Kiring"}
      </button>
    </form>
  );
}
