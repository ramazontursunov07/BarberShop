import { useState } from "react";
import { api, tokens } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";

export default function Profile() {
  const { user } = useAuth();
  const { t } = useI18n();
  const [hasPassword, setHasPassword] = useState(user.has_password);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSaved(false);
    setBusy(true);
    try {
      const data = await api("/api/users/set-password/", {
        method: "POST",
        body: { current_password: current, new_password: next },
      });
      // Parol o'zgargach eski tokenlar bekor bo'ladi: yangilarini saqlaymiz
      tokens.set(data.access, data.refresh);
      setHasPassword(true);
      setCurrent("");
      setNext("");
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <h1>{t("profile.title")}</h1>
      <div className="card">
        <p><strong>{[user.first_name, user.last_name].filter(Boolean).join(" ")}</strong></p>
        <p className="muted">{t("profile.phone")}: {user.phone}</p>
        <p className={user.is_phone_verified ? "" : "error"}>
          {user.is_phone_verified ? t("profile.verified") : t("profile.not_verified")}
        </p>
      </div>

      <form className="card form" onSubmit={submit} style={{ marginTop: "1rem" }}>
        <h2>{hasPassword ? t("profile.pw_change") : t("profile.pw_title")}</h2>
        {!hasPassword && <p className="muted">{t("profile.pw_none")}</p>}

        {hasPassword && (
          <label>
            {t("profile.current")}
            <input type="password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
          </label>
        )}
        <label>
          {t("profile.new")}
          <input type="password" value={next} onChange={(e) => setNext(e.target.value)} minLength={8} required />
        </label>

        {error && <p className="error">{error}</p>}
        {saved && <p>{t("profile.saved")}</p>}

        <button className="btn" disabled={busy}>{busy ? t("wait") : t("profile.save")}</button>
      </form>
    </>
  );
}
