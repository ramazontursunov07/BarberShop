import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, results } from "../api.js";
import { useI18n } from "../i18n.jsx";

export default function Shops() {
  const { t } = useI18n();
  const [shops, setShops] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const data = await api("/api/shops/", { query: { search }, auth: false });
        if (!cancelled) {
          setShops(results(data));
          setError("");
        }
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [search]);

  return (
    <>
      <h1>{t("shops.title")}</h1>
      <input className="search" placeholder={t("shops.search")} value={search} onChange={(e) => setSearch(e.target.value)} />

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">{t("loading")}</p>}
      {!loading && !error && shops.length === 0 && <p className="muted">{t("shops.empty")}</p>}

      <div className="list">
        {shops.map((s) => (
          <Link key={s.id} to={`/shop/${s.id}`} className="card shop">
            <h3>{s.name}</h3>
            <p className="muted">{[s.city, s.district, s.address].filter(Boolean).join(", ")}</p>
            <p>
              🕘 {s.opens_at?.slice(0, 5)} – {s.closes_at?.slice(0, 5)}
              {s.avg_rating != null && (
                <span className="rating">
                  ⭐ {s.avg_rating} <small>({s.reviews_count})</small>
                </span>
              )}
            </p>
          </Link>
        ))}
      </div>
    </>
  );
}
