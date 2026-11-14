import { useEffect, useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import BookingsTab from "../owner/BookingsTab.jsx";
import QueueTab from "./QueueTab.jsx";
import ScheduleTab from "./ScheduleTab.jsx";
import EarningsTab from "./EarningsTab.jsx";

const TABS = ["today", "queue", "schedule", "earnings"];

export default function MasterPanel() {
  const { t } = useI18n();
  const [me, setMe] = useState(null);
  const [tab, setTab] = useState("today");
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);

  useEffect(() => {
    api("/api/masters/me/")
      .then(setMe)
      .catch((e) => setError(e.status === 403 ? t("ms.not_master") : e.message));
  }, [version, t]);

  if (error) return <p className="error">{error}</p>;
  if (!me) return <p className="muted">{t("loading")}</p>;

  return (
    <>
      <h1>{t("ms.title")}</h1>
      <p className="muted">{me.name} · {me.shop_name}</p>
      {!me.is_active && <p className="error">{t("ms.inactive")}</p>}

      <div className="tabs">
        {TABS.map((k) => (
          <button key={k} className={`tab ${tab === k ? "active" : ""}`} onClick={() => setTab(k)}>
            {t(`ms.tab_${k}`)}
          </button>
        ))}
      </div>

      {tab === "today" && <BookingsTab shopName={me.shop_name} />}
      {tab === "queue" && <QueueTab me={me} />}
      {tab === "schedule" && <ScheduleTab me={me} onChanged={() => setVersion((v) => v + 1)} />}
      {tab === "earnings" && <EarningsTab />}
    </>
  );
}
