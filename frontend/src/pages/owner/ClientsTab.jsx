import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import { money } from "../../format.js";

function ClientDetail({ shopId, clientId }) {
  const { t } = useI18n();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/insights/clients/${clientId}/`, { query: { shop: shopId } })
      .then(setData)
      .catch((e) => setError(e.message));
  }, [shopId, clientId]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">{t("loading")}</p>;

  return (
    <div className="panel">
      <p>{t("cl.fav_master")}: <strong>{data.favorite_master?.name ?? "—"}</strong></p>
      <p>{t("cl.fav_service")}: <strong>{data.favorite_service?.name ?? "—"}</strong></p>
      <h3>{t("cl.history")}</h3>
      {data.history.map((h) => (
        <p key={h.id} className="muted">
          {h.date} · {h.service} · {h.master} · {money(h.price, t)} · {t(`status.${h.status}`)}
        </p>
      ))}
    </div>
  );
}

export default function ClientsTab({ shopId }) {
  const { t } = useI18n();
  const [search, setSearch] = useState("");
  const [ordering, setOrdering] = useState("last_visit");
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      api("/api/insights/clients/", { query: { shop: shopId, search, ordering } })
        .then((d) => !cancelled && (setClients(d.clients), setError("")))
        .catch((e) => !cancelled && setError(e.message))
        .finally(() => !cancelled && setLoading(false));
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [shopId, search, ordering]);

  return (
    <>
      <div className="row">
        <input className="search grow" placeholder={t("cl.search")} value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="search" value={ordering} onChange={(e) => setOrdering(e.target.value)}>
          <option value="last_visit">{t("cl.sort_last")}</option>
          <option value="visits">{t("cl.sort_visits")}</option>
          <option value="spent">{t("cl.sort_spent")}</option>
          <option value="no_shows">{t("cl.sort_no_shows")}</option>
        </select>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">{t("loading")}</p>}
      {!loading && clients.length === 0 && <p className="muted">{t("cl.empty")}</p>}

      <div className="list">
        {clients.map((c) => (
          <div key={c.id} className="card">
            <button className="option plain" onClick={() => setOpenId(openId === c.id ? null : c.id)}>
              <strong>{c.name || c.phone}</strong>
              <span className="muted">{c.phone}</span>
              <span>
                {c.visits} {t("cl.visits")} · {t("cl.spent")}: {money(c.total_spent, t)}
                {c.no_shows > 0 && ` · ${t("cl.no_shows")}: ${c.no_shows}`}
                {c.cancelled > 0 && ` · ${t("cl.cancelled")}: ${c.cancelled}`}
              </span>
              {c.last_visit && <small className="muted">{t("cl.last")}: {c.last_visit}</small>}
            </button>
            {openId === c.id && <ClientDetail shopId={shopId} clientId={c.id} />}
          </div>
        ))}
      </div>
    </>
  );
}
