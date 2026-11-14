import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import { money, todayISO } from "../../format.js";

export default function EarningsTab() {
  const { t } = useI18n();
  const today = todayISO();
  const [from, setFrom] = useState(`${today.slice(0, 8)}01`);
  const [to, setTo] = useState(today);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/masters/me/earnings/", { query: { from, to } })
      .then((d) => (setData(d), setError("")))
      .catch((e) => setError(e.message));
  }, [from, to]);

  return (
    <>
      <h2>{t("er.title")}</h2>
      <div className="row">
        <label className="muted">{t("er.from")} <input type="date" className="search" value={from} max={to} onChange={(e) => e.target.value && setFrom(e.target.value)} /></label>
        <label className="muted">{t("er.to")} <input type="date" className="search" value={to} min={from} onChange={(e) => e.target.value && setTo(e.target.value)} /></label>
      </div>
      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="muted">{t("loading")}</p>}
      {data && (
        <>
          <div className="cards">
            <div className="card stat"><small>{t("er.share")} ({data.commission_percent}%)</small><strong>{money(data.master_share, t)}</strong></div>
            <div className="card stat"><small>{t("er.revenue")}</small><strong>{money(data.revenue, t)}</strong></div>
            <div className="card stat"><small>{t("er.bookings")}</small><strong>{data.bookings}</strong></div>
          </div>

          {data.bookings === 0 ? (
            <p className="muted">{t("er.empty")}</p>
          ) : (
            <>
              <h2>{t("er.methods")}</h2>
              <div className="card">
                {["cash", "card", "transfer", "unspecified"].filter((k) => data[k] > 0).map((k) => (
                  <div key={k} className="row" style={{ justifyContent: "space-between" }}>
                    <span>{t(`pay.${k}`)}</span><strong>{money(data[k], t)}</strong>
                  </div>
                ))}
              </div>

              <h2>{t("er.days")}</h2>
              <div className="list">
                {data.days.map((d) => (
                  <div key={d.date} className="card booking">
                    <div><strong>{d.date}</strong><p className="muted">{d.bookings} {t("st.bookings")} · {money(d.revenue, t)}</p></div>
                    <strong>{money(d.master_share, t)}</strong>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
