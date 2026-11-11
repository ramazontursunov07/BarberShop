import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, results } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { money, todayISO } from "../format.js";

const stars = (n) => "★".repeat(n) + "☆".repeat(5 - n);

export default function ShopPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();

  const [shop, setShop] = useState(null);
  const [services, setServices] = useState([]);
  const [masters, setMasters] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [faq, setFaq] = useState([]);
  const [loadError, setLoadError] = useState("");

  const [serviceId, setServiceId] = useState(null);
  const [masterId, setMasterId] = useState(null);
  const [date, setDate] = useState(todayISO());
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [time, setTime] = useState("");

  const [booking, setBooking] = useState(false);
  const [bookError, setBookError] = useState("");
  const [waitlisted, setWaitlisted] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const optional = (promise) => promise.catch(() => []);
    Promise.all([
      api(`/api/shops/${id}/`, { auth: false }),
      api("/api/services/", { query: { shop: id }, auth: false }),
      api("/api/masters/", { query: { shop: id }, auth: false }),
      optional(api("/api/reviews/", { query: { shop: id }, auth: false })),
      optional(api("/api/faq/", { query: { shop: id }, auth: false })),
    ])
      .then(([s, sv, m, rv, fq]) => {
        if (cancelled) return;
        setShop(s);
        setServices(results(sv));
        setMasters(results(m));
        setReviews(results(rv));
        setFaq(results(fq));
      })
      .catch((err) => !cancelled && setLoadError(err.status === 404 ? t("shop.not_found") : err.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Bo'sh vaqtlar: xizmat, usta va sana tanlanganda (kirgan foydalanuvchi uchun)
  useEffect(() => {
    setTime("");
    setSlots([]);
    setWaitlisted(false);
    setBookError("");
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

  const joinWaitlist = async () => {
    setBookError("");
    setBooking(true);
    try {
      await api("/api/bookings/waitlist/", { method: "POST", body: { service: serviceId, master: masterId, date } });
      setWaitlisted(true);
    } catch (err) {
      setBookError(err.message);
    } finally {
      setBooking(false);
    }
  };

  if (loadError) return <p className="error">{loadError}</p>;
  if (!shop) return <p className="muted">{t("loading")}</p>;


  return (
    <>
      <Link to="/" className="back">{t("back")}</Link>
      <h1>{shop.name}</h1>
      <p className="muted">{[shop.city, shop.district, shop.address].filter(Boolean).join(", ")}</p>
      <p>
        📞 {shop.phone} · 🕘 {shop.opens_at?.slice(0, 5)} – {shop.closes_at?.slice(0, 5)}
        {shop.avg_rating != null && (
          <span className="rating">⭐ {shop.avg_rating} <small>({shop.reviews_count})</small></span>
        )}
      </p>
      {shop.description && <p>{shop.description}</p>}

      {shop.photos?.length > 0 && (
        <div className="gallery">
          {shop.photos.map((p) => (
            <img key={p.id} src={p.image} alt={shop.name} loading="lazy" />
          ))}
        </div>
      )}

      <h2>{t("shop.step1")}</h2>
      <div className="list">
        {services.map((s) => (
          <button key={s.id} className={`card option ${serviceId === s.id ? "active" : ""}`} onClick={() => setServiceId(s.id)}>
            <strong>{s.name}</strong>
            <span>{money(s.price, t)} · {s.duration_minutes} {t("minutes")}</span>
          </button>
        ))}
        {services.length === 0 && <p className="muted">{t("shop.no_services")}</p>}
      </div>

      <h2>{t("shop.step2")}</h2>
      <div className="list">
        {masters.map((m) => (
          <button key={m.id} className={`card option ${masterId === m.id ? "active" : ""}`} onClick={() => setMasterId(m.id)}>
            <strong>{m.name}</strong>
            <span>{m.avg_rating != null ? `⭐ ${m.avg_rating} (${m.reviews_count})` : t("shop.not_rated")}</span>
            {m.bio && <small className="muted">{m.bio}</small>}
          </button>
        ))}
        {masters.length === 0 && <p className="muted">{t("shop.no_masters")}</p>}
      </div>

      <h2>{t("shop.step3")}</h2>
      {!user ? (
        <div className="card">
          {t("shop.login_needed")}{" "}
          <Link to="/login" state={{ from: `/shop/${id}` }}>{t("shop.login_link")}</Link>.
        </div>
      ) : (
        <>
          <input type="date" className="search" value={date} min={todayISO()} onChange={(e) => setDate(e.target.value)} />
          {!serviceId || !masterId ? (
            <p className="muted">{t("shop.pick_first")}</p>
          ) : slotsLoading ? (
            <p className="muted">{t("shop.searching")}</p>
          ) : slots.length === 0 ? (
            <div>
              <p className="muted">{t("shop.no_slots")}</p>
              {waitlisted ? (
                <p>✅ {t("shop.waitlist_done")}</p>
              ) : (
                <button className="btn" onClick={joinWaitlist} disabled={booking}>
                  {booking ? t("wait") : t("shop.waitlist")}
                </button>
              )}
            </div>
          ) : (
            <div className="slots">
              {slots.map((s) => (
                <button key={s} className={`slot ${time === s ? "active" : ""}`} onClick={() => setTime(s)}>
                  {s}
                </button>
              ))}
            </div>
          )}

          {time && service && (
            <div className="card summary">
              <p><strong>{service.name}</strong> · {date} · {time}</p>
              <p>{t("shop.price")}: {money(service.price, t)}</p>
              {bookError && <p className="error">{bookError}</p>}
              <button className="btn" onClick={submit} disabled={booking}>
                {booking ? t("wait") : t("shop.book")}
              </button>
            </div>
          )}
          {!time && bookError && <p className="error">{bookError}</p>}
        </>
      )}

      {faq.length > 0 && (
        <>
          <h2>{t("shop.faq")}</h2>
          <div className="list">
            {faq.map((f) => (
              <details key={f.id} className="card">
                <summary>{f.question}</summary>
                <p className="muted">{f.answer}</p>
              </details>
            ))}
          </div>
        </>
      )}

      <h2>{t("shop.reviews")}</h2>
      {reviews.length === 0 && <p className="muted">{t("shop.no_reviews")}</p>}
      <div className="list">
        {reviews.map((r) => (
          <div key={r.id} className="card">
            <p>
              <span className="stars">{stars(r.rating)}</span> <strong>{r.client_name}</strong>
            </p>
            <p className="muted">{r.service} · {r.master_name}</p>
            {r.comment && <p>{r.comment}</p>}
          </div>
        ))}
      </div>
    </>
  );
}
