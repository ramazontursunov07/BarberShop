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

/* ---------- Jamoa: ustalarni qo'shish va boshqarish ---------- */
function TeamRow({ m, onChanged, onError }) {
  const { t } = useI18n();
  const [percent, setPercent] = useState(m.commission_percent);
  const [busy, setBusy] = useState(false);
  const dirty = Number(percent) !== m.commission_percent;

  const patch = async (body) => {
    setBusy(true); onError("");
    try { await api(`/api/masters/my/${m.id}/`, { method: "PATCH", body }); onChanged(); }
    catch (e) { onError(e.message); } finally { setBusy(false); }
  };
  const toggle = () => {
    if (m.is_active && m.upcoming_bookings > 0 && !window.confirm(t("mg.deactivate_confirm", { n: m.upcoming_bookings }))) return;
    patch({ is_active: !m.is_active });
  };

  return (
    <div className="card booking" style={{ opacity: m.is_active ? 1 : 0.55 }}>
      <div>
        <strong>{m.name}</strong> · <a href={`tel:${m.phone}`}>{m.phone}</a>
        {m.upcoming_bookings > 0 && <p className="muted">{t("mg.upcoming", { n: m.upcoming_bookings })}</p>}
      </div>
      <div className="row" style={{ margin: 0 }}>
        <label className="muted">{t("adm.commission")} %
          <input className="search" type="number" min="0" max="100" style={{ width: 90 }} value={percent} onChange={(e) => setPercent(e.target.value)} />
        </label>
        {dirty && <button className="btn" disabled={busy} onClick={() => patch({ commission_percent: Number(percent) })}>{t("mg.save")}</button>}
        <button className={`btn ${m.is_active ? "danger" : "ghost"}`} disabled={busy} onClick={toggle}>
          {m.is_active ? t("adm.deactivate") : t("adm.activate")}
        </button>
      </div>
    </div>
  );
}

function Team({ shopId, onChanged }) {
  const { t } = useI18n();
  const blank = { phone: "+998", first_name: "", last_name: "", commission_percent: 50, password: "" };
  const [team, setTeam] = useState(null);
  const [form, setForm] = useState(blank);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = () => api("/api/masters/my/team/", { query: { shop: shopId } }).then(setTeam).catch((e) => setError(e.message));
  useEffect(() => { load(); }, [shopId]); // eslint-disable-line
  const changed = () => { load(); onChanged(); };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const add = async (e) => {
    e.preventDefault();
    setBusy(true); setError(""); setCreated(null);
    try {
      const res = await api("/api/masters/my/team/", { method: "POST", body: { ...form, shop: shopId, commission_percent: Number(form.commission_percent) } });
      setCreated({ phone: res.master.phone, password: res.temp_password });
      setForm(blank);
      changed();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  };

  return (
    <>
      <h2>{t("mg.team")}</h2>
      {team && team.length === 0 && <p className="muted">{t("adm.no_masters")}</p>}
      <div className="list">
        {(team || []).map((m) => <TeamRow key={m.id} m={m} onChanged={changed} onError={setError} />)}
      </div>

      <form className="card form" onSubmit={add}>
        <strong>{t("adm.add_master")}</strong>
        <div className="row">
          <input className="search grow" value={form.phone} onChange={set("phone")} placeholder="+998901234567" inputMode="tel" required />
          <input className="search grow" value={form.first_name} onChange={set("first_name")} placeholder={t("first_name")} required />
          <input className="search grow" value={form.last_name} onChange={set("last_name")} placeholder={t("last_name")} />
        </div>
        <div className="row">
          <label className="muted">{t("adm.commission")} %
            <input className="search" type="number" min="0" max="100" value={form.commission_percent} onChange={set("commission_percent")} />
          </label>
          <input className="search grow" value={form.password} onChange={set("password")} placeholder={t("adm.owner_password")} autoComplete="off" />
        </div>
        <p className="muted">{t("adm.master_hint")} {t("mg.team_hint")}</p>
        {error && <p className="error">{error}</p>}
        {created && <p className="ok">{t("adm.master_created")}</p>}
        {created?.password && (
          <div className="card summary">
            <p>{t("mg.temp_pw")}</p>
            <p>{t("adm.login_phone")}: <strong>{created.phone}</strong></p>
            <p>{t("password")}: <strong style={{ fontFamily: "monospace", userSelect: "all" }}>{created.password}</strong></p>
          </div>
        )}
        <button className="btn" disabled={busy}>{busy ? t("wait") : t("adm.add_master")}</button>
      </form>
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

function Masters({ shopId, version }) {
  const { t } = useI18n();
  const [masters, setMasters] = useState([]);
  useEffect(() => {
    fetchAll("/api/masters/my/").then((l) => setMasters(l.filter((m) => m.shop === shopId))).catch(() => setMasters([]));
  }, [shopId, version]);
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

/* ---------- Sartaroshxona ma'lumotlari ---------- */
function ShopInfo({ shopId }) {
  const { t } = useI18n();
  const [f, setF] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api(`/api/shops/my/${shopId}/`)
      .then((s) => setF({ ...s, opens_at: hhmm(s.opens_at), closes_at: hhmm(s.closes_at) }))
      .catch((e) => setError(e.message));
  }, [shopId]);

  if (!f) return error ? <p className="error">{error}</p> : <p className="muted">{t("loading")}</p>;
  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setMsg(""); };

  const locate = () => {
    if (!navigator.geolocation) return setError(t("home.no_geo"));
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setF((cur) => ({ ...cur, latitude: pos.coords.latitude.toFixed(6), longitude: pos.coords.longitude.toFixed(6) }));
        setMsg(t("mg.location_set"));
        setError("");
      },
      () => setError(t("home.no_geo")),
      { timeout: 10000 }
    );
  };

  const save = async () => {
    setBusy(true); setError(""); setMsg("");
    try {
      const body = {
        name: f.name, description: f.description || "", phone: f.phone, city: f.city, district: f.district || "",
        address: f.address, opens_at: f.opens_at, closes_at: f.closes_at,
        latitude: f.latitude === "" || f.latitude == null ? null : String(f.latitude),
        longitude: f.longitude === "" || f.longitude == null ? null : String(f.longitude),
      };
      const s = await api(`/api/shops/my/${shopId}/`, { method: "PATCH", body });
      setF({ ...s, opens_at: hhmm(s.opens_at), closes_at: hhmm(s.closes_at) });
      setMsg(t("mg.saved"));
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };

  return (
    <>
      <h2>{t("mg.shop_info")}</h2>
      <div className="card form" style={{ marginTop: 0 }}>
        <label>{t("mg.shop_name")}<input value={f.name || ""} onChange={set("name")} maxLength={120} /></label>
        <label>{t("mg.shop_desc")}<textarea rows={3} value={f.description || ""} onChange={set("description")} /></label>
        <label>{t("mg.shop_phone")}<input value={f.phone || ""} onChange={set("phone")} inputMode="tel" /></label>
        <div className="row">
          <label className="grow">{t("mg.shop_city")}<input value={f.city || ""} onChange={set("city")} /></label>
          <label className="grow">{t("mg.shop_district")}<input value={f.district || ""} onChange={set("district")} /></label>
        </div>
        <label>{t("mg.shop_address")}<input value={f.address || ""} onChange={set("address")} /></label>
        <div className="row">
          <label className="grow">{t("mg.opens")}<input type="time" value={f.opens_at || ""} onChange={set("opens_at")} /></label>
          <label className="grow">{t("mg.closes")}<input type="time" value={f.closes_at || ""} onChange={set("closes_at")} /></label>
        </div>
        <div className="row">
          <button type="button" className="btn ghost" onClick={locate}>📍 {t("mg.use_location")}</button>
          {f.latitude != null && f.latitude !== "" && (
            <a href={`https://www.google.com/maps/search/?api=1&query=${f.latitude},${f.longitude}`} target="_blank" rel="noreferrer">
              {f.latitude}, {f.longitude}
            </a>
          )}
        </div>
        {error && <p className="error">{error}</p>}
        {msg && <p className="ok">{msg}</p>}
        <button className="btn" onClick={save} disabled={busy || !f.name}>{busy ? t("wait") : t("mg.save")}</button>
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

  const remove = async (id) => {
    if (!window.confirm(t("mg.photo_delete_confirm"))) return;
    setError("");
    try { await api(`/api/shops/photos/${id}/`, { method: "DELETE" }); load(); } catch (err) { setError(err.message); }
  };

  return (
    <>
      <h2>{t("mg.gallery")}</h2>
      <div className="gallery">
        {photos.map((p) => (
          <div key={p.id} style={{ position: "relative", flex: "none" }}>
            <img src={p.image} alt="" />
            <button className="icon-btn" onClick={() => remove(p.id)} aria-label={t("mg.delete")} title={t("mg.delete")}
              style={{ position: "absolute", top: 6, right: 6, width: 30, height: 30, background: "rgba(0,0,0,.6)", color: "#fff", border: 0 }}>✕</button>
          </div>
        ))}
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
  const [version, setVersion] = useState(0);
  return (
    <>
      <ShopInfo shopId={shopId} />
      <Services shopId={shopId} />
      <Team shopId={shopId} onChanged={() => setVersion((v) => v + 1)} />
      <Masters shopId={shopId} version={version} />
      <Faq shopId={shopId} />
      <Gallery shopId={shopId} />
    </>
  );
}
