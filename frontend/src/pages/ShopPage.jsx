import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, results } from "../api.js";
import { useAuth } from "../auth.jsx";
import { money, todayISO } from "../format.js";

export default function ShopPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [shop, setShop] = useState(null);
  const [services, setServices] = useState([]);
  const [masters, setMasters] = useState([]);
  const [loadError, setLoadError] = useState("");

  const [serviceId, setServiceId] = useState(null);
  const [masterId, setMasterId] = useState(null);
  const [date, setDate] = useState(todayISO());
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [time, setTime] = useState("");

  const [booking, setBooking] = useState(false);
  const [bookError, setBookError] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api(`/api/shops/${id}/`, { auth: false }),
      api("/api/services/", { query: { shop: id }, auth: false }),
      api("/api/masters/", { query: { shop: id }, auth: false }),
    ])
      .then(([s, sv, m]) => {
        if (cancelled) return;
        setShop(s);
        setServices(results(sv));
        setMasters(results(m));
      })
      .catch((err) => !cancelled && setLoadError(err.status === 404 ? "Sartaroshxona topilmadi" : err.message));
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Bo'sh vaqtlar: xizmat, usta va sana tanlanganda (kirgan foydalanuvchi uchun)
  useEffect(() => {
    setTime("");
    setSlots([]);
    if (!user || !serviceId || !masterId || !date) return;
    let cancelled = false;
    setSlotsLoading(true);
    api("/api/bookings/slots/", { query: { master: masterId, service: serviceId, date } })
      .then((data) => !cancelled && setSlots(data.slots || []))
      .catch((err) => !cancelled && setBookError(err.message))
      .finally(() => !cancelled && setSlotsLoading(false));
    return () => {
      cancelled = true;
    };
  }, [user, serviceId, masterId, date]);

  const service = services.find((s) => s.id === serviceId);

  const submit = async () => {
    setBookError("");
    setBooking(true);
    try {
      await api("/api/bookings/", {
        method: "POST",
        body: { master: masterId, service: serviceId, date, start_time: time },
      });
      navigate("/bookings");
    } catch (err) {
      setBookError(err.message);
    } finally {
      setBooking(false);
    }
  };

  if (loadError) return <p className="error">{loadError}</p>;
  if (!shop) return <p className="muted">Yuklanmoqda...</p>;

  return (
    <>
      <Link to="/" className="back">← Orqaga</Link>
      <h1>{shop.name}</h1>
      <p className="muted">{[shop.city, shop.district, shop.address].filter(Boolean).join(", ")}</p>
      <p>
        📞 {shop.phone} · 🕘 {shop.opens_at?.slice(0, 5)} – {shop.closes_at?.slice(0, 5)}
        {shop.avg_rating != null && <span className="rating">⭐ {shop.avg_rating} <small>({shop.reviews_count})</small></span>}
      </p>
      {shop.description && <p>{shop.description}</p>}

      {shop.photos?.length > 0 && (
        <div className="gallery">
          {shop.photos.map((p) => (
            <img key={p.id} src={p.image} alt={shop.name} loading="lazy" />
          ))}
        </div>
      )}

      <h2>1. Xizmatni tanlang</h2>
      <div className="list">
        {services.map((s) => (
          <button key={s.id} className={`card option ${serviceId === s.id ? "active" : ""}`} onClick={() => setServiceId(s.id)}>
            <strong>{s.name}</strong>
            <span>{money(s.price)} · {s.duration_minutes} daqiqa</span>
          </button>
        ))}
        {services.length === 0 && <p className="muted">Xizmatlar hali qo'shilmagan.</p>}
      </div>

      <h2>2. Ustani tanlang</h2>
      <div className="list">
        {masters.map((m) => (
          <button key={m.id} className={`card option ${masterId === m.id ? "active" : ""}`} onClick={() => setMasterId(m.id)}>
            <strong>{m.name}</strong>
            <span>
              {m.avg_rating != null ? `⭐ ${m.avg_rating} (${m.reviews_count})` : "Hali baholanmagan"}
            </span>
            {m.bio && <small className="muted">{m.bio}</small>}
          </button>
        ))}
        {masters.length === 0 && <p className="muted">Ustalar hali qo'shilmagan.</p>}
      </div>

      <h2>3. Sana va vaqt</h2>
      {!user ? (
        <div className="card">
          Bo'sh vaqtlarni ko'rish va bron qilish uchun{" "}
          <Link to="/login" state={{ from: `/shop/${id}` }}>kiring</Link>.
        </div>
      ) : (
        <>
          <input type="date" className="search" value={date} min={todayISO()} onChange={(e) => setDate(e.target.value)} />
          {!serviceId || !masterId ? (
            <p className="muted">Avval xizmat va ustani tanlang.</p>
          ) : slotsLoading ? (
            <p className="muted">Bo'sh vaqtlar qidirilmoqda...</p>
          ) : slots.length === 0 ? (
            <p className="muted">Bu kunga bo'sh vaqt yo'q. Boshqa sana yoki ustani tanlang.</p>
          ) : (
            <div className="slots">
              {slots.map((t) => (
                <button key={t} className={`slot ${time === t ? "active" : ""}`} onClick={() => setTime(t)}>
                  {t}
                </button>
              ))}
            </div>
          )}

          {time && service && (
            <div className="card summary">
              <p>
                <strong>{service.name}</strong> · {date} · {time}
              </p>
              <p>Narxi: {money(service.price)}</p>
              {bookError && <p className="error">{bookError}</p>}
              <button className="btn" onClick={submit} disabled={booking}>
                {booking ? "Kuting..." : "Bron qilish"}
              </button>
            </div>
          )}
          {!time && bookError && <p className="error">{bookError}</p>}
        </>
      )}
    </>
  );
}
