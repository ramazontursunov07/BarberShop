import { useEffect, useState } from "react";
import { fetchAll } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { useI18n } from "../../i18n.jsx";
import BookingsTab from "./BookingsTab.jsx";
import StatsTab from "./StatsTab.jsx";
import ClientsTab from "./ClientsTab.jsx";

export default function OwnerPanel() {
  const { user } = useAuth();
  const { t } = useI18n();
  const isOwner = user.role === "owner";

  const [shops, setShops] = useState([]);
  const [shopId, setShopId] = useState(null);
  const [tab, setTab] = useState("today");
  const [loading, setLoading] = useState(isOwner);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isOwner) return;
    fetchAll("/api/shops/my/")
      .then((list) => {
        setShops(list);
        setShopId(list[0]?.id ?? null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [isOwner]);

  if (loading) return <p className="muted">{t("loading")}</p>;
  if (error) return <p className="error">{error}</p>;
  if (isOwner && shops.length === 0) return <p className="muted">{t("own.no_shops")}</p>;

  const shop = shops.find((s) => s.id === shopId);
  const tabs = isOwner ? ["today", "stats", "clients"] : ["today"];

  return (
    <>
      <h1>{t("own.title")}</h1>

      {isOwner && shops.length > 1 && (
        <select className="search" value={shopId} onChange={(e) => setShopId(Number(e.target.value))}>
          {shops.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
      )}
      {isOwner && shops.length === 1 && <p className="muted">{shop.name}</p>}

      {tabs.length > 1 && (
        <div className="tabs">
          {tabs.map((k) => (
            <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>
              {t(`own.tab_${k}`)}
            </button>
          ))}
        </div>
      )}

      {tab === "today" && <BookingsTab shopName={shop?.name} />}
      {tab === "stats" && <StatsTab shopId={shopId} />}
      {tab === "clients" && <ClientsTab shopId={shopId} />}
    </>
  );
}
