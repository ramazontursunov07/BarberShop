import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, results, tokens } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { dateTime } from "../format.js";
import Icon from "../components/Icon.jsx";
import { Avatar } from "../components/ui.jsx";

export default function Profile() {
  const { user, logout } = useAuth();
  const { t, lang } = useI18n();
  const [next, setNext] = useState(null);
  const [hasPassword, setHasPassword] = useState(!!user?.has_password);
  const [current, setCurrent] = useState("");
  const [newPw, setNewPw] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setSaved(false);
    setBusy(true);
    try {
      const data = await api("/api/users/set-password/", { method: "POST", body: { current_password: current, new_password: newPw } });
      tokens.set(data.access, data.refresh); // eski tokenlar bekor bo'ladi
      setHasPassword(true);
      setCurrent("");
      setNewPw("");
      setSaved(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    api("/api/bookings/")
      .then((d) => {
        const list = results(d).filter((b) => ["pending", "confirmed"].includes(b.status) && new Date(b.start_time) > new Date());
        list.sort((a, b) => a.start_time.localeCompare(b.start_time));
        setNext(list[0] || null);
      })
      .catch(() => {});
  }, []);

  if (!user) return null;
  const name = `${user.first_name || ""} ${user.last_name || ""}`.trim() || user.phone;

  return (
    <>
      <div className="card" style={{ marginTop: "1rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <Avatar name={name} />
        <div className="grow"><h2 style={{ margin: 0 }}>{name}</h2><p className="muted">{user.phone} · {t(`role.${user.role}`)}</p></div>
      </div>

      {next && (
        <>
          <h2>{t("profile.next")}</h2>
          <Link to="/bookings" className="card option active">
            <strong>{next.service_name}</strong>
            <span className="muted">{next.master_name} · {dateTime(next.start_time, lang)}</span>
          </Link>
        </>
      )}

      <h2>{t("profile.menu")}</h2>
      <div className="list">
        <Link to="/bookings" className="card"><Icon name="calendar" size={18} style={{ verticalAlign: "-4px" }} /> {t("nav.bookings")}</Link>
        <Link to="/assistant" className="card"><Icon name="sparkle" size={18} style={{ verticalAlign: "-4px" }} /> {t("nav.ai")}</Link>
        <Link to="/hairstyle" className="card"><Icon name="camera" size={18} style={{ verticalAlign: "-4px" }} /> {t("style.title")}</Link>
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
          <input type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} minLength={8} required />
        </label>

        {error && <p className="error">{error}</p>}
        {saved && <p>{t("profile.saved")}</p>}

        <button className="btn" disabled={busy}>{busy ? t("wait") : t("profile.save")}</button>
      </form>

      <button className="btn ghost block" style={{ marginTop: "1.5rem" }} onClick={logout}>{t("nav.logout")}</button>
    </>
  );
}
