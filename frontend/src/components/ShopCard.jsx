import { Link } from "react-router-dom";
import { useI18n } from "../i18n.jsx";
import { isOpenNow } from "../format.js";
import Icon from "./Icon.jsx";

export default function ShopCard({ shop }) {
  const { t } = useI18n();
  const open = isOpenNow(shop.opens_at, shop.closes_at);
  return (
    <Link to={`/shop/${shop.id}`} className="card shop-card">
      <div className="cover">
        {shop.cover ? <img src={shop.cover} alt={shop.name} loading="lazy" /> : <Icon name="scissors" size={42} stroke={1.3} />}
        <div className="chips">
          {open != null && <span className={`chip ${open ? "ok" : "off"}`}>{open ? t("home.open") : t("home.closed")}</span>}
          {shop.avg_rating != null && <span className="chip"><Icon name="star" size={13} fill="currentColor" /> {shop.avg_rating}</span>}
        </div>
      </div>
      <div className="body">
        <h3>{shop.name}</h3>
        <p className="muted">{[shop.city, shop.district, shop.address].filter(Boolean).join(", ")}</p>
        <div className="meta">
          <span><Icon name="clock" size={14} /> {shop.opens_at?.slice(0, 5)} – {shop.closes_at?.slice(0, 5)}</span>
          {shop.distance_km != null ? <span className="chip gold">{shop.distance_km} km</span> : <span>{shop.reviews_count ? `${shop.reviews_count} ${t("home.reviews")}` : ""}</span>}
        </div>
      </div>
    </Link>
  );
}
