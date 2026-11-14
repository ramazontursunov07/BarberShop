import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import AdminShops from "./AdminShops.jsx";
import NewShopForm from "./NewShopForm.jsx";
import AdminUsers from "./AdminUsers.jsx";

const STATS = [
  ["shops_total", "adm.s_shops"],
  ["shops_pending", "adm.s_pending"],
  ["masters", "adm.s_masters"],
  ["clients", "adm.s_clients"],
  ["bookings_30d", "adm.s_bookings"],
];

export default function AdminPanel() {
  const { t } = useI18n();
  const [tab, setTab] = useState("shops");
  const [stats, setStats] = useState(null);
  const [version, setVersion] = useState(0); // ro'yxat/ko'rsatkichlarni qayta yuklash uchun

  useEffect(() => {
    api("/api/admin/stats/").then(setStats).catch(() => setStats(null));
  }, [version]);

  const refresh = () => setVersion((v) => v + 1);

  return (
    <>
      <h1>{t("adm.title")}</h1>

      {stats && (
        <div className="cards">
          {STATS.map(([key, label]) => (
            <div key={key} className="card stat">
              <small>{t(label)}</small>
              <strong>{stats[key]}</strong>
            </div>
          ))}
        </div>
      )}

      <div className="tabs">
        {["shops", "new", "users"].map((k) => (
          <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>
            {t(`adm.tab_${k}`)}
          </button>
        ))}
      </div>

      {tab === "shops" && <AdminShops version={version} onChanged={refresh} />}
      {tab === "new" && (
        <NewShopForm
          onCreated={() => {
            refresh();
          }}
          onOpenList={() => setTab("shops")}
        />
      )}
      {tab === "users" && <AdminUsers />}
    </>
  );
}
