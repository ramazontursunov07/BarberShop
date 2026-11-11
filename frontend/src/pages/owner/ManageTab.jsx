import { useEffect, useState } from "react";
import { api, fetchAll } from "../../api.js";
import { useI18n } from "../../i18n.jsx";

const WEEKDAYS = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"];
const hhmm = (v) => (v || "").slice(0, 5);

/* ---------- Xizmatlar va narxlar ---------- */
function ServiceRow({ s, onSaved, onError }) {
  const { t } = useI18n();
  const [f, setF] = useState({ name: s.name, price: s.price, duration_minutes: s.duration_minutes });
  const [busy, setBusy] = useState(false);
  const dirty = f.name !== s.name || String(f.price) !== String(s.price) || Number(f.duration_minutes) !== s.duration_minutes;

  const save = async () => {
    setBusy(true);
    try {
      await api(`/api/services/my/${s.id}/`, { method: "PATCH", body: { ...f, price: String(f.price), duration_minutes: Number(f.duration_minutes) } });
      onSaved();
    } catch (e) { onError(e.message); } finally { setBusy(false); }
  };
  const toggle = async () => {
    try {
      if (s.is_active) await api(`/api/services/my/${s.id}/`, { method: "DELETE" });
      else await api(`/api/services/my/${s.id}/`, { method: "PATCH", body: { is_active: true } });
      onSaved();
    } catch (e) { onError(e.message); }
  };

  return (
    <div className="card" style={{ opacity: s.is_active ? 1 : 0.55 }}>
      <input className="search" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
      <div className="row">
        <label className="muted">{t("mg.price")} ({t("currency")})
          <input className="search" type="number" min="0" value={f.price} onChange={(e) => setF({ ...f, price: e.target.value })} />
        </label>
        <label className="muted">{t("minutes")}
          <input className="search" type="number" min="5" step="5" value={f.duration_minutes} onChange={(e) => setF({ ...f, duration_minutes: e.target.value })} />
        </label>
      </div>
      <div className="row">
        {dirty && <button className="btn" onClick={save} disabled={busy}>{busy ? t("wait") : t("mg.save")}</button>}
        <button className={`btn ${s.is_active ? "danger" : "ghost"}`} onClick={toggle}>
          {s.is_active ? t("mg.hide") : t("mg.show")}
        </button>
      </div>
    </div>
  );
}

function Services({ shopId }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [nw, setNw] = useState({ name: "", price: "", duration_minutes: 30 });

  const load = () => fetchAll("/api/services/my/", { shop: shopId }).then(setItems).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [shopId]); // eslint-disable-line

  const add = async () => {
    setError("");
    try {
      await api("/api/services/my/", { method: "POST", body: { shop: shopId, name: nw.name, price: String(nw.price), duration_minutes: Number(nw.duration_minutes) } });
      setNw({ name: "", price: "", duration_minutes: 30 });
      load();
    } catch (e) { setError(e.message); }
  };

  return (
    <>
      <h2>{t("mg.services")}</h2>
      {error && <p className="error">{error}</p>}
      <div className="list">
        {items.map((s) => <ServiceRow key={`${s.id}-${s.price}-${s.name}-${s.duration_minutes}-${s.is_active}`} s={s} onSaved={load} onError={setError} />)}
        <div className="card">
          <strong>{t("mg.add_service")}</strong>
          <input className="search" placeholder={t("mg.name")} value={nw.name} onChange={(e) => setNw({ ...nw, name: e.target.value })} />
          <div className="row">
            <input className="search" type="number" min="0" placeholder={t("mg.price")} value={nw.price} onChange={(e) => setNw({ ...nw, price: e.target.value })} />
            <input className="search" type="number" min="5" step="5" value={nw.duration_minutes} onChange={(e) => setNw({ ...nw, duration_minutes: e.target.value })} />
          </div>
          <button className="btn" onClick={add} disabled={!nw.name || !nw.price}>{t("mg.add")}</button>
        </div>
      </div>
    </>
  );
}

/* ---------- Ustalar jadvali ---------- */
function ScheduleEditor({ master }) {
  const { t } = useI18n();
  const [days, setDays] = useState(null); // {weekday: {on, start, end}}
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/masters/my/${master.id}/schedule/`).then((rows) => {
      const d = {};
      for (let i = 0; i < 7; i++) d[i] = { on: false, start: "09:00", end: "18:00" };
      rows.forEach((r) => (d[r.weekday] = { on: true, start: hhmm(r.start_time), end: hhmm(r.end_time) }));
      setDays(d);
    }).catch((e) => setError(e.message));
  }, [master.id]);

  const set = (i, patch) => { setMsg(""); setDays({ ...days, [i]: { ...days[i], ...patch } }); };
  const save = async () => {
    setError(""); setMsg("");
    const schedules = Object.entries(days).filter(([, v]) => v.on).map(([k, v]) => ({ weekday: Number(k), start_time: v.start, end_time: v.end }));
    try {
      await api(`/api/masters/my/${master.id}/schedule/`, { method: "PUT", body: { schedules } });
      setMsg(t("mg.saved"));
    } catch (e) { setError(e.message); }
  };

  if (!days) return <p className="muted">{error || t("loading")}</p>;
  return (
    <div className="card">
      <strong>{master.name}</strong>
      {WEEKDAYS.map((name, i) => (
        <div key={i} className="row" style={{ alignItems: "center" }}>
          <label style={{ minWidth: 110 }}>
            <input type="checkbox" checked={days[i].on} onChange={(e) => set(i, { on: e.target.checked })} /> {t(`wd.${name}`)}
          </label>
          {days[i].on ? (
            <>
              <input type="time" className="search" value={days[i].start} onChange={(e) => set(i, { start: e.target.value })} />
              <input type="time" className="search" value={days[i].end} onChange={(e) => set(i, { end: e.target.value })} />
            </>
          ) : <span className="muted">{t("mg.day_off")}</span>}
        </div>
      ))}
      {error && <p className="error">{error}</p>}
      {msg && <p style={{ color: "var(--ok)" }}>{msg}</p>}
      <button className="btn" onClick={save}>{t("mg.save")}</button>
    </div>
  );
}

function Masters({ shopId }) {
  const { t } = useI18n();
  const [masters, setMasters] = useState([]);
  useEffect(() => {
    fetchAll("/api/masters/my/").then((l) => setMasters(l.filter((m) => m.shop === shopId))).catch(() => setMasters([]));
  }, [shopId]);
  return (
    <>
      <h2>{t("mg.schedule")}</h2>
      <div className="list">
        {masters.map((m) => <ScheduleEditor key={m.id} master={m} />)}
        {masters.length === 0 && <p className="muted">{t("shop.no_masters")}</p>}
      </div>
    </>
  );
}

/* ---------- FAQ ---------- */
function Faq({ shopId }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  const [nw, setNw] = useState({ question: "", answer: "" });

  const load = () => fetchAll("/api/faq/my/").then((l) => setItems(l.filter((f) => f.shop === shopId))).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [shopId]); // eslint-disable-line

  const add = async () => {
    setError("");
    try {
      await api("/api/faq/my/", { method: "POST", body: { shop: shopId, ...nw, position: items.length } });
      setNw({ question: "", answer: "" });
      load();
    } catch (e) { setError(e.message); }
  };
  const remove = async (id) => {
    if (!window.confirm(t("mg.delete_confirm"))) return;
    try { await api(`/api/faq/my/${id}/`, { method: "DELETE" }); load(); } catch (e) { setError(e.message); }
  };

  return (
    <>
      <h2>{t("shop.faq")}</h2>
      {error && <p className="error">{error}</p>}
      <div className="list">
        {items.map((f) => (
          <div key={f.id} className="card">
            <strong>{f.question}</strong>
            <p className="muted">{f.answer}</p>
            <button className="btn danger" onClick={() => remove(f.id)}>{t("mg.delete")}</button>
          </div>
        ))}
        <div className="card">
          <input className="search" placeholder={t("mg.question")} value={nw.question} onChange={(e) => setNw({ ...nw, question: e.target.value })} />
          <textarea className="search" rows={3} placeholder={t("mg.answer")} value={nw.answer} onChange={(e) => setNw({ ...nw, answer: e.target.value })} />
          <button className="btn" onClick={add} disabled={!nw.question || !nw.answer}>{t("mg.add")}</button>
          <p className="muted">{t("mg.faq_hint")}</p>
        </div>
      </div>
    </>
  );
}

/* ---------- Galereya ---------- */
function Gallery({ shopId }) {
  const { t } = useI18n();
  const [photos, setPhotos] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () => api(`/api/shops/${shopId}/`, { auth: false }).then((s) => setPhotos(s.photos || [])).catch(() => {});
  useEffect(() => { load(); }, [shopId]); // eslint-disable-line

  const upload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true); setError("");
    try {
      const fd = new FormData();
      fd.append("shop", shopId);
      fd.append("image", file);
      const token = localStorage.getItem("access");
      const res = await fetch("/api/shops/photos/", { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: fd });
      if (!res.ok) throw new Error(Object.values(await res.json().catch(() => ({})))[0] || "Xatolik");
      load();
    } catch (err) { setError(String(err.message)); } finally { setBusy(false); e.target.value = ""; }
  };

  return (
    <>
      <h2>{t("mg.gallery")}</h2>
      <div className="gallery">
        {photos.map((p) => <img key={p.id} src={p.image} alt="" />)}
      </div>
      {error && <p className="error">{error}</p>}
      <label className="btn ghost" style={{ display: "inline-block", marginTop: ".5rem" }}>
        {busy ? t("wait") : t("mg.upload")}
        <input type="file" accept="image/*" hidden onChange={upload} disabled={busy} />
      </label>
    </>
  );
}

export default function ManageTab({ shopId }) {
  return (
    <>
      <Services shopId={shopId} />
      <Masters shopId={shopId} />
      <Faq shopId={shopId} />
      <Gallery shopId={shopId} />
    </>
  );
}
