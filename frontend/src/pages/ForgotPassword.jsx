import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { useToast } from "../components/Toast.jsx";
import { PasswordInput } from "../components/ui.jsx";

// Parolni tiklash: 1) telefon -> Telegram'ga kod, 2) kod + yangi parol.
export default function ForgotPassword() {
  const { t } = useI18n();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [phone, setPhone] = useState("+998");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const requestCode = async (e) => {
    e?.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/api/users/password-reset/request/", { method: "POST", body: { phone }, auth: false });
      setStep(2);
    } catch (err) {
      setError(err.status === 429 ? t("fp.too_many") : err.message);
    } finally {
      setBusy(false);
    }
  };

  const confirm = async (e) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api("/api/users/password-reset/confirm/", {
        method: "POST",
        body: { phone, code: code.trim(), new_password: password },
        auth: false,
      });
      toast(t("fp.done"));
      navigate("/login", { replace: true });
    } catch (err) {
      if (err.status === 429) setError(t("fp.too_many"));
      else if (err.data?.new_password) setError(err.data.new_password.join(" "));
      else if (err.status === 400) setError(t("fp.bad_code"));
      else setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card auth">
      <aside className="auth-side">
        <span className="brand-mark">✂</span>
        <h2>{t("fp.title")}</h2>
        <ul>
          <li>{t("fp.p1")}</li>
          <li>{t("fp.p2")}</li>
        </ul>
      </aside>

      {step === 1 ? (
        <form className="form auth-form" onSubmit={requestCode}>
          <h2>{t("fp.title")}</h2>
          <p className="muted">{t("fp.step1")}</p>
          <label>
            {t("phone")}
            <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+998901234567" inputMode="tel" autoComplete="tel" required />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="btn block" disabled={busy}>{busy ? t("wait") : t("fp.send")}</button>
          <Link className="link" to="/login">{t("fp.back")}</Link>
        </form>
      ) : (
        <form className="form auth-form" onSubmit={confirm}>
          <h2>{t("fp.title")}</h2>
          <p className="muted">{t("fp.step2")}</p>
          <label>
            {t("fp.code")}
            <input
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="123456"
              maxLength={6}
              required
              autoFocus
            />
          </label>
          <label>
            {t("profile.new")}
            <PasswordInput
              label_show={t("pw.show")}
              label_hide={t("pw.hide")}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              autoComplete="new-password"
              required
            />
          </label>
          {error && <p className="error">{error}</p>}
          <button className="btn block" disabled={busy || code.length < 6}>{busy ? t("wait") : t("fp.save")}</button>
          <button type="button" className="link" disabled={busy} onClick={requestCode}>{t("fp.resend")}</button>
          <button type="button" className="link" onClick={() => { setStep(1); setError(""); }}>{t("fp.change_phone")}</button>
        </form>
      )}
    </div>
  );
}
