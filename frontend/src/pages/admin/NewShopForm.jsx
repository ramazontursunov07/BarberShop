import { useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import TempPassword from "./TempPassword.jsx";

const EMPTY_SHOP = {
  name: "", description: "", phone: "+998", city: "Toshkent", district: "", address: "",
  opens_at: "09:00", closes_at: "20:00", latitude: "", longitude: "",
};
const EMPTY_OWNER = { phone: "+998", first_name: "", last_name: "", password: "" };

export default function NewShopForm({ onCreated, onOpenList }) {
  const { t } = useI18n();
  const [shop, setShop] = useState(EMPTY_SHOP);
  const [owner, setOwner] = useState(EMPTY_OWNER);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(null);

  const setS = (k) => (e) => setShop({ ...shop, [k]: e.target.value });
  const setO = (k) => (e) => setOwner({ ...owner, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    setDone(null);
    // Bo'sh koordinata maydonlari yuborilmaydi (null bo'lib qoladi)
    const body = Object.fromEntries(Object.entries(shop).filter(([k, v]) => !(["latitude", "longitude", "district", "description"].includes(k) && v === "")));
    try {
      const res = await api("/api/admin/shops/", { method: "POST", body: { shop: body, owner } });
      setDone({ name: res.shop.name, ownerPhone: res.shop.owner_phone, password: res.temp_password });
      setShop(EMPTY_SHOP);
      setOwner(EMPTY_OWNER);
      onCreated();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="card form" onSubmit={submit}>
      <h2>{t("adm.new_title")}</h2>

      <strong>{t("adm.shop_data")}</strong>
      <label>{t("adm.name")}<input value={shop.name} onChange={setS("name")} required /></label>
      <label>{t("adm.description")}<textarea className="search" rows={2} value={shop.description} onChange={setS("description")} /></label>
      <label>{t("adm.shop_phone")}<input value={shop.phone} onChange={setS("phone")} inputMode="tel" required /></label>
      <div className="row">
        <label className="grow">{t("adm.city")}<input value={shop.city} onChange={setS("city")} required /></label>
        <label className="grow">{t("adm.district")}<input value={shop.district} onChange={setS("district")} /></label>
      </div>
      <label>{t("adm.address")}<input value={shop.address} onChange={setS("address")} required /></label>
      <div className="row">
        <label>{t("adm.opens")}<input type="time" value={shop.opens_at} onChange={setS("opens_at")} required /></label>
        <label>{t("adm.closes")}<input type="time" value={shop.closes_at} onChange={setS("closes_at")} required /></label>
        <label className="grow">{t("adm.lat")}<input type="number" step="0.000001" min="-90" max="90" value={shop.latitude} onChange={setS("latitude")} placeholder="41.311081" /></label>
        <label className="grow">{t("adm.lng")}<input type="number" step="0.000001" min="-180" max="180" value={shop.longitude} onChange={setS("longitude")} placeholder="69.240562" /></label>
      </div>

      <strong>{t("adm.owner_data")}</strong>
      <label>{t("adm.owner_phone")}<input value={owner.phone} onChange={setO("phone")} inputMode="tel" required /></label>
      <div className="row">
        <label className="grow">{t("first_name")}<input value={owner.first_name} onChange={setO("first_name")} /></label>
        <label className="grow">{t("last_name")}<input value={owner.last_name} onChange={setO("last_name")} /></label>
      </div>
      <label>{t("adm.owner_password")}<input type="text" value={owner.password} onChange={setO("password")} autoComplete="off" /></label>
      <p className="muted">{t("adm.owner_hint")}</p>

      {error && <p className="error">{error}</p>}
      {done && (
        <>
          <p style={{ color: "var(--ok)" }}>{t("adm.created")} {done.name}</p>
          <TempPassword phone={done.ownerPhone} password={done.password} />
          <button type="button" className="link" onClick={onOpenList}>{t("adm.tab_shops")} →</button>
        </>
      )}
      <button className="btn" disabled={busy}>{busy ? t("wait") : t("adm.create")}</button>
    </form>
  );
}
