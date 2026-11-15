import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, results } from "../api.js";
import { useI18n } from "../i18n.jsx";

function ShopCard({ s }) {
  return (
    <Link to={`/shop/${s.id}`} className="card shop-card">
      <div className="shop-cover">
        {s.cover ? <img src={s.cover} alt={s.name} loading="lazy" /> : <div className="ph">{s.name?.[0]?.toUpperCase()}</div>}
        {s.avg_rating != null && (
          <span className="rate">
            ⭐ {s.avg_rating} <small>({s.reviews_count})</small>
          </span>
        )}
      </div>
      <div className="shop-body">
        <h3>{s.name}</h3>
        <p className="muted">📍 {[s.city, s.district, s.address].filter(Boolean).join(", ")}</p>
        <p className="muted">🕘 {s.opens_at?.slice(0, 5)} – {s.closes_at?.slice(0, 5)}</p>
      </div>
    </Link>
  );
}

export default function Shops() {
  const { t } = useI18n();
  const [shops, setShops] = useState([]);
  const [search, setSearch] = useState("");
  const [city, setCity] = useState("");
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

  const cities = useMemo(() => [...new Set(shops.map((s) => s.city).filter(Boolean))], [shops]);
  const visible = city ? shops.filter((s) => s.city === city) : shops;

  return (
    <>
      <section className="hero">
        <span className="hero-art">✂</span>
        <h1>{t("hero.title")}</h1>
        <p>{t("hero.sub")}</p>
        <div className="search-wrap">
          <span>🔍</span>
          <input className="search" placeholder={t("shops.search")} value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {cities.length > 1 && (
          <div className="chips">
            <button className={`chip ${city === "" ? "active" : ""}`} onClick={() => setCity("")}>{t("shops.all")}</button>
            {cities.map((c) => (
              <button key={c} className={`chip ${city === c ? "active" : ""}`} onClick={() => setCity(c)}>{c}</button>
            ))}
          </div>
        )}
      </section>

      {error && <p className="error">{error}</p>}
      {!loading && !error && visible.length > 0 && <p className="muted">{t("shops.found", { n: visible.length })}</p>}

      {loading && (
        <div className="grid">
          {[0, 1, 2].map((i) => <div key={i} className="skeleton" />)}
        </div>
      )}

      {!loading && !error && visible.length === 0 && (
        <div className="empty"><span className="big">💈</span>{t("shops.empty")}</div>
      )}

      {!loading && (
        <div className="grid">
          {visible.map((s) => <ShopCard key={s.id} s={s} />)}
        </div>
      )}
    </>
  );
}
