import { useCallback, useEffect, useState } from "react";
import { api, fetchAll } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import TempPassword from "./TempPassword.jsx";

const FILTERS = ["", "pending", "approved", "inactive"];

function MastersBox({ shop, onChanged }) {
  const { t } = useI18n();
  const [masters, setMasters] = useState(null);
  const [form, setForm] = useState({ phone: "+998", first_name: "", last_name: "", commission_percent: 50, password: "" });
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    api(`/api/admin/shops/${shop.id}/masters/`).then(setMasters).catch((e) => setError(e.message));
  }, [shop.id]);

  useEffect(load, [load]);

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const add = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setCreated(null);
    try {
      const res = await api(`/api/admin/shops/${shop.id}/masters/`, {
        method: "POST",
        body: { ...form, commission_percent: Number(form.commission_percent) },
      });
      setCreated({ phone: res.master.phone, password: res.temp_password });
      setForm({ phone: "+998", first_name: "", last_name: "", commission_percent: 50, password: "" });
      load();
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (m) => {
    try {
      await api(`/api/admin/masters/${m.id}/`, { method: "PATCH", body: { is_active: !m.is_active } });
      load();
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="panel">
      <h3>{t("adm.masters_title")}</h3>
      {masters && masters.length === 0 && <p className="muted">{t("adm.no_masters")}</p>}
      <div className="list">
        {(masters || []).map((m) => (
          <div key={m.id} className="card booking" style={{ opacity: m.is_active ? 1 : 0.55 }}>
            <div>
              <strong>{m.name}</strong> · <a href={`tel:${m.phone}`}>{m.phone}</a>
              <p className="muted">{t("adm.commission")}: {m.commission_percent}%</p>
            </div>
            <button className={`btn ${m.is_active ? "danger" : "ghost"}`} onClick={() => toggle(m)}>
              {m.is_active ? t("adm.deactivate") : t("adm.activate")}
            </button>
          </div>
        ))}
      </div>

      <form className="form" onSubmit={add}>
        <strong>{t("adm.add_master")}</strong>
        <div className="row">
          <input className="search grow" value={form.phone} onChange={set("phone")} placeholder="+998901234567" inputMode="tel" required />
          <input className="search grow" value={form.first_name} onChange={set("first_name")} placeholder={t("first_name")} />
          <input className="search grow" value={form.last_name} onChange={set("last_name")} placeholder={t("last_name")} />
        </div>
        <div className="row">
          <label className="muted">{t("adm.commission")}
            <input className="search" type="number" min="0" max="100" value={form.commission_percent} onChange={set("commission_percent")} />
          </label>
          <input className="search grow" type="text" value={form.password} onChange={set("password")} placeholder={t("adm.owner_password")} autoComplete="off" />
        </div>
        <p className="muted">{t("adm.master_hint")}</p>
        {error && <p className="error">{error}</p>}
        {created && <p style={{ color: "var(--ok)" }}>{t("adm.master_created")}</p>}
        <TempPassword {...created} />
        <button className="btn" disabled={busy}>{busy ? t("wait") : t("adm.add_master")}</button>
      </form>
    </div>
  );
}

function ShopCard({ shop, onChanged }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const patch = async (body) => {
    setError("");
    try {
      await api(`/api/admin/shops/${shop.id}/`, { method: "PATCH", body });
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="card" style={{ opacity: shop.is_active ? 1 : 0.6 }}>
      <div className="booking">
        <div>
          <h3>{shop.name}</h3>
          <p className="muted">{shop.city}{shop.district ? `, ${shop.district}` : ""} · {shop.address}</p>
          <p>{t("adm.owner")}: {shop.owner_name} · <a href={`tel:${shop.owner_phone}`}>{shop.owner_phone}</a></p>
          <p className="muted">{shop.masters_count} {t("adm.masters")} · {shop.services_count} {t("adm.services")}</p>
        </div>
        <div className="right">
          {!shop.is_active ? (
            <span className="badge cancelled">{t("adm.inactive_badge")}</span>
          ) : !shop.is_approved ? (
            <span className="badge pending">{t("adm.pending_badge")}</span>
          ) : (
            <span className="badge completed">{t("adm.f_approved")}</span>
          )}
          {shop.is_active && !shop.is_approved && (
            <button className="btn ghost" onClick={() => patch({ is_approved: true })}>{t("adm.approve")}</button>
          )}
          {shop.is_active ? (
            <button className="btn danger" onClick={() => window.confirm(`${shop.name}: ${t("adm.deactivate")}?`) && patch({ is_active: false })}>
              {t("adm.deactivate")}
            </button>
          ) : (
            <button className="btn ghost" onClick={() => patch({ is_active: true })}>{t("adm.activate")}</button>
          )}
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      <button className="link" onClick={() => setOpen(!open)}>{open ? "▾" : "▸"} {t("adm.masters_title")}</button>
      {open && <MastersBox shop={shop} onChanged={onChanged} />}
    </div>
  );
}

export default function AdminShops({ version, onChanged }) {
  const { t } = useI18n();
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      fetchAll("/api/admin/shops/", { q, state })
        .then((list) => !cancelled && (setItems(list), setError("")))
        .catch((e) => !cancelled && setError(e.message))
        .finally(() => !cancelled && setLoading(false));
    }, 250); // yozayotganda har harfga so'rov yubormaslik uchun
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [q, state, version]);

  return (
    <>
      <input className="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t("adm.search")} />
      <div className="tabs small">
        {FILTERS.map((f) => (
          <button key={f || "all"} className={`tab ${state === f ? "active" : ""}`} onClick={() => setState(f)}>
            {t(`adm.f_${f || "all"}`)}
          </button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">{t("loading")}</p>}
      {!loading && items.length === 0 && <p className="muted">{t("adm.empty")}</p>}
      <div className="list">
        {items.map((s) => (
          <ShopCard key={s.id} shop={s} onChanged={onChanged} />
        ))}
      </div>
    </>
  );
}
