import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import { money, percent } from "../../format.js";

function Bars({ rows, label, value, suffix, empty }) {
  const max = Math.max(1, ...rows.map(value));
  if (rows.length === 0) return <p className="muted">{empty}</p>;
  return (
    <div className="bars">
      {rows.map((r, i) => (
        <div key={i} className="bar-row">
          <div className="bar-head">
            <span>{label(r)}</span>
            <span className="muted">{suffix(r)}</span>
          </div>
          <div className="bar"><div style={{ width: `${(value(r) / max) * 100}%` }} /></div>
        </div>
      ))}
    </div>
  );
}

export default function StatsTab({ shopId }) {
  const { t } = useI18n();
  const [days, setDays] = useState(30);
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setData(null);
    api("/api/insights/stats/", { query: { shop: shopId, days } })
      .then((d) => !cancelled && (setData(d), setError("")))
      .catch((e) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [shopId, days]);

  return (
    <>
      <div className="tabs small">
        {[7, 30, 90].map((n) => (
          <button key={n} className={`tab ${days === n ? "active" : ""}`} onClick={() => setDays(n)}>
            {t("own.last_days", { n })}
          </button>
        ))}
      </div>

      {error && <p className="error">{error}</p>}
      {!data && !error && <p className="muted">{t("loading")}</p>}

      {data && (
        <>
          <div className="cards">
            <div className="card stat"><small>{t("st.revenue")}</small><strong>{money(data.revenue, t)}</strong></div>
            <div className="card stat"><small>{t("st.completed")}</small><strong>{data.completed}</strong></div>
            <div className="card stat"><small>{t("st.avg")}</small><strong>{money(data.average_check, t)}</strong></div>
            <div className="card stat"><small>{t("st.no_show")}</small><strong>{percent(data.no_show_rate)}</strong></div>
            <div className="card stat"><small>{t("st.cancel")}</small><strong>{percent(data.cancel_rate)}</strong></div>
            <div className="card stat"><small>{t("own.total")}</small><strong>{data.total_bookings}</strong></div>
          </div>

          <h2>{t("st.top")}</h2>
          <Bars
            rows={data.top_services}
            label={(r) => r.service}
            value={(r) => r.bookings}
            suffix={(r) => `${r.bookings} ${t("st.bookings")} · ${money(r.revenue, t)}`}
            empty={t("st.empty")}
          />

          <h2>{t("st.hours")}</h2>
          <Bars
            rows={data.busiest_hours.slice(0, 8)}
            label={(r) => r.hour}
            value={(r) => r.bookings}
            suffix={(r) => `${r.bookings} ${t("st.bookings")}`}
            empty={t("st.empty")}
          />

          <h2>{t("st.days")}</h2>
          <Bars
            rows={data.busiest_weekdays}
            label={(r) => t(`wd.${r.weekday}`)}
            value={(r) => r.bookings}
            suffix={(r) => `${r.bookings} ${t("st.bookings")}`}
            empty={t("st.empty")}
          />

          <h2>{t("st.masters")}</h2>
          <Bars
            rows={data.masters}
            label={(r) => r.master}
            value={(r) => r.revenue}
            suffix={(r) => `${r.bookings} ${t("st.bookings")} · ${money(r.revenue, t)}`}
            empty={t("st.empty")}
          />
        </>
      )}
    </>
  );
}
