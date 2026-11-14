import { useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import { todayISO } from "../../format.js";

const WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"];

export default function ScheduleTab({ me, onChanged }) {
  const { t } = useI18n();
  const [date, setDate] = useState("");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const byDay = Object.fromEntries(me.schedule.map((s) => [s.weekday, s]));

  const add = async (e) => {
    e.preventDefault();
    if (!window.confirm(t("sc.confirm"))) return;
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await api(`/api/masters/${me.id}/days-off/`, { method: "POST", body: { date, reason } });
      setMsg(t("sc.added", { n: res.cancelled_bookings }));
      setDate("");
      setReason("");
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const remove = async (d) => {
    setError("");
    try {
      await api(`/api/masters/${me.id}/days-off/${d}/`, { method: "DELETE" });
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <>
      <h2>{t("sc.title")}</h2>
      <div className="card">
        {WEEKDAYS.map((name, i) => (
          <div key={i} className="row" style={{ justifyContent: "space-between" }}>
            <span>{t(`wd.${name}`)}</span>
            {byDay[i] ? <strong>{byDay[i].start_time}–{byDay[i].end_time}</strong> : <span className="muted">{t("sc.off")}</span>}
          </div>
        ))}
        <p className="muted">{t("sc.readonly")}</p>
      </div>

      <h2>{t("sc.days_off")}</h2>
      {me.days_off.length === 0 && <p className="muted">{t("sc.none")}</p>}
      <div className="list">
        {me.days_off.map((d) => (
          <div key={d.date} className="card booking">
            <div><strong>{d.date}</strong>{d.reason && <p className="muted">{d.reason}</p>}</div>
            <button className="btn ghost" onClick={() => remove(d.date)}>{t("sc.remove")}</button>
          </div>
        ))}
      </div>

      <form className="card form" onSubmit={add}>
        <strong>{t("sc.add_day_off")}</strong>
        <div className="row">
          <label>{t("sc.date")}<input type="date" min={todayISO()} value={date} onChange={(e) => setDate(e.target.value)} required /></label>
          <label className="grow">{t("sc.reason")}<input value={reason} maxLength={100} onChange={(e) => setReason(e.target.value)} /></label>
        </div>
        <p className="muted">{t("sc.warn")}</p>
        {error && <p className="error">{error}</p>}
        {msg && <p style={{ color: "var(--ok)" }}>{msg}</p>}
        <button className="btn" disabled={busy || !date}>{busy ? t("wait") : t("sc.add_day_off")}</button>
      </form>
    </>
  );
}
