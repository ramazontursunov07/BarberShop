import { useEffect, useState } from "react";
import { api, fetchAll } from "../../api.js";
import { useI18n } from "../../i18n.jsx";

const ROLES = ["", "client", "master", "owner", "admin"];

export default function AdminUsers() {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchAll("/api/admin/users/", { q, role })
        .then((list) => !cancelled && (setItems(list), setError("")))
        .catch((e) => !cancelled && setError(e.message));
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [q, role, version]);

  const toggle = async (u) => {
    try {
      await api(`/api/admin/users/${u.id}/`, { method: "PATCH", body: { is_active: !u.is_active } });
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <>
      <div className="row">
        <input className="search grow" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("adm.users_search")} />
        <select className="search" value={role} onChange={(e) => setRole(e.target.value)}>
          {ROLES.map((r) => (
            <option key={r || "all"} value={r}>{r ? t(`role.${r}`) : t("adm.all_roles")}</option>
          ))}
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p className="muted">{t("adm.empty")}</p>}
      <div className="list">
        {items.map((u) => (
          <div key={u.id} className="card booking" style={{ opacity: u.is_active ? 1 : 0.55 }}>
            <div>
              <strong>{u.first_name} {u.last_name}</strong> <span className="badge">{t(`role.${u.role}`)}</span>
              <p><a href={`tel:${u.phone}`}>{u.phone}</a></p>
              {u.no_show_count > 0 && <p className="muted">{u.no_show_count} {t("adm.no_show")}</p>}
            </div>
            {u.role !== "admin" && (
              <button className={`btn ${u.is_active ? "danger" : "ghost"}`} onClick={() => toggle(u)}>
                {u.is_active ? t("adm.block") : t("adm.unblock")}
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
