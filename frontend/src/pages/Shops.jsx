import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, results } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import Icon from "../components/Icon.jsx";
import ShopCard from "../components/ShopCard.jsx";
import { Empty, ShopSkeletons } from "../components/ui.jsx";
import { useToast } from "../components/Toast.jsx";

export default function Shops() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useToast();
  const navigate = useNavigate();
  const [shops, setShops] = useState([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [near, setNear] = useState(null);
  const [locating, setLocating] = useState(false);

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

  const locate = () => {
    if (!navigator.geolocation) return toast(t("home.no_geo"), "err");
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        try {
          const data = await api("/api/shops/nearby/", {
            query: { lat: pos.coords.latitude, lng: pos.coords.longitude, radius_km: 15, limit: 6 },
            auth: false,
          });
          const list = (Array.isArray(data) ? data : results(data)).map((s) => ({ ...s, avg_rating: s.rating, reviews_count: 0 }));
          setNear(list);
          if (list.length === 0) toast(t("home.no_near"), "err");
        } catch (e) {
          toast(e.message, "err");
        } finally {
          setLocating(false);
        }
      },
      () => {
        setLocating(false);
        toast(t("home.no_geo"), "err");
      },
      { timeout: 10000 }
    );
  };

  return (
    <>
      <section className="hero">
        <h1>{t("home.title_a")} <em>{t("home.title_b")}</em></h1>
        <p className="sub">{t("home.sub")}</p>
        <div className="searchbar">
          <Icon name="search" size={19} />
          <input placeholder={t("shops.search")} value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="quick">
          <button onClick={locate} disabled={locating}>
            <span className="ic"><Icon name="nav" size={20} /></span>{locating ? "…" : t("home.q_near")}
          </button>
          <Link to="/assistant"><span className="ic"><Icon name="sparkle" size={20} /></span>{t("home.q_ai")}</Link>
          <Link to="/hairstyle"><span className="ic"><Icon name="camera" size={20} /></span>{t("home.q_style")}</Link>
          <button onClick={() => navigate(user ? "/bookings" : "/login")}>
            <span className="ic"><Icon name="calendar" size={20} /></span>{t("nav.bookings")}
          </button>
        </div>
      </section>

      {near && near.length > 0 && (
        <>
          <div className="section-head"><h2>{t("home.near")}</h2>
            <button className="link" onClick={() => setNear(null)}>{t("bk.close")}</button></div>
          <div className="shop-grid">{near.map((s) => <ShopCard key={`n${s.id}`} shop={s} />)}</div>
        </>
      )}

      <div className="section-head">
        <h2>{search ? t("home.results") : t("shops.title")}</h2>
        {!loading && <span className="muted">{shops.length}</span>}
      </div>
      {error && <p className="error">{error}</p>}
      {loading && shops.length === 0 ? (
        <ShopSkeletons />
      ) : shops.length === 0 && !error ? (
        <Empty icon="search">{t("shops.empty")}</Empty>
      ) : (
        <div className="shop-grid">{shops.map((s) => <ShopCard key={s.id} shop={s} />)}</div>
      )}
    </>
  );
}
