import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, results } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { money, shiftDate, todayISO } from "../format.js";

const stars = (n) => "★".repeat(n) + "☆".repeat(5 - n);
const DATE_LOCALE = { uz: "uz-UZ", ru: "ru-RU", en: "en-GB" };
const initials = (name = "") => name.split(" ").map((w) => w[0]).slice(0, 2).join("").toUpperCase();

function Step({ n, title }) {
  return (
    <div className="step-head">
      <span className="step-no">{n}</span>
      <h2>{title}</h2>
    </div>
  );
}

function DatePicker({ value, onChange, lang }) {
  const days = useMemo(() => Array.from({ length: 14 }, (_, i) => shiftDate(todayISO(), i)), []);
  const fmt = (iso, opts) => new Date(`${iso}T00:00:00Z`).toLocaleDateString(DATE_LOCALE[lang] || "ru-RU", { timeZone: "UTC", ...opts });
  return (
    <div className="dates">
      {days.map((d) => (
        <button key={d} className={`date-chip ${value === d ? "active" : ""}`} onClick={() => onChange(d)}>
          <small>{fmt(d, { weekday: "short" })}</small>
          <strong>{fmt(d, { day: "numeric" })}</strong>
          <small>{fmt(d, { month: "short" })}</small>
        </button>
      ))}
    </div>
  );
}

function Loyalty({ data, t }) {
  const pct = data.reward_available ? 100 : Math.round(((data.every_n_visits - data.visits_to_next_reward) / data.every_n_visits) * 100);
  return (
    <div className="card loyalty">
      <div className="loyalty-top">
        <strong>🎁 {t("shop.loyalty")}</strong>
        <span className="chip accent static">{t("shop.loyalty_text", { n: data.every_n_visits, p: data.discount_percent })}</span>
      </div>
      <div className="progress"><div style={{ width: `${pct}%` }} /></div>
      <small className={data.reward_available ? "ok" : "muted"}>
        {data.reward_available ? t("shop.loyalty_ready") : t("shop.loyalty_left", { n: data.visits_to_next_reward })}
      </small>
    </div>
  );
}

function Offers({ items, t }) {
  return (
    <>
      <h2>🔥 {t("shop.offers")}</h2>
      <div className="offers">
        {items.map((o) => (
          <div key={o.code} className="offer">
            <code>{o.code}</code>
            <strong>{o.percent ? `-${o.percent}%` : `-${money(o.amount, t)}`} {t("offer.off")}</strong>
            <small className="muted">{o.description || (o.first_visit_only ? t("offer.first") : "")}</small>
            {o.valid_until && <small className="muted">{t("offer.until")} {o.valid_until.slice(0, 10)}</small>}
          </div>
        ))}
      </div>
    </>
  );
}

function Products({ items, user, shopId, t }) {
  const [reserved, setReserved] = useState(new Set());
  const [msg, setMsg] = useState("");
  const navigate = useNavigate();

  const reserve = async (id) => {
    if (!user) return navigate("/login", { state: { from: `/shop/${shopId}` } });
    setMsg("");
    try {
      await api("/api/products/reservations/", { method: "POST", body: { product: id, quantity: 1 } });
      setReserved((prev) => new Set(prev).add(id));
    } catch (err) {
      setMsg(err.message);
    }
  };

  return (
    <>
      <h2>🛍️ {t("shop.products")}</h2>
      <p className="muted">{t("shop.products_hint")}</p>
      {msg && <p className="error">{msg}</p>}
      <div className="products">
        {items.map((p) => (
          <div key={p.id} className="card product">
            <div className="pimg">{p.image ? <img src={p.image} alt={p.name} loading="lazy" /> : "🧴"}</div>
            <div className="pbody">
              <strong>{p.name}</strong>
              {p.category && <small className="muted">{p.category}</small>}
              <span className="price">{money(p.price, t)}</span>
              {reserved.has(p.id) ? (
                <span className="ok">{t("shop.reserved")}</span>
              ) : p.in_stock ? (
                <button className="btn ghost" onClick={() => reserve(p.id)}>{t("shop.reserve")}</button>
              ) : (
                <small className="muted">{t("shop.out_of_stock")}</small>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

export default function ShopPage() {
  const { id } = useParams();
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const navigate = useNavigate();

  const [shop, setShop] = useState(null);
  const [services, setServices] = useState([]);
  const [masters, setMasters] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [faq, setFaq] = useState([]);
  const [offers, setOffers] = useState([]);
  const [products, setProducts] = useState([]);
  const [loyalty, setLoyalty] = useState(null);
  const [loadError, setLoadError] = useState("");

  const [serviceId, setServiceId] = useState(null);
  const [masterId, setMasterId] = useState(null);
  const [date, setDate] = useState(todayISO());
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [time, setTime] = useState("");

  const [promo, setPromo] = useState("");
  const [cert, setCert] = useState("");
  const [quote, setQuote] = useState(null);
  const [quoteError, setQuoteError] = useState("");

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
      optional(api("/api/promotions/offers/", { query: { shop: id }, auth: false })),
      optional(api("/api/products/", { query: { shop: id }, auth: false })),
    ])
      .then(([s, sv, m, rv, fq, of, pr]) => {
        if (cancelled) return;
        setShop(s);
        setServices(results(sv));
        setMasters(results(m));
        setReviews(results(rv));
        setFaq(results(fq));
        setOffers(results(of));
        setProducts(results(pr));
      })
      .catch((err) => !cancelled && setLoadError(err.status === 404 ? t("shop.not_found") : err.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Sodiqlik holati: faqat kirgan foydalanuvchi uchun (dastur bo'lmasa 404 -> ko'rsatilmaydi)
  useEffect(() => {
    setLoyalty(null);
    if (!user) return;
    let cancelled = false;
    api("/api/promotions/loyalty/", { query: { shop: id } })
      .then((d) => !cancelled && setLoyalty(d))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [user, id]);

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

  // Yakuniy narx (sodiqlik, promokod, sertifikat bilan): bron yaratmasdan oldindan hisoblanadi
  useEffect(() => {
    setQuote(null);
    setQuoteError("");
    if (!user || !serviceId || !time) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      api("/api/promotions/quote/", {
        method: "POST",
        body: { service: serviceId, date, start_time: time, promo_code: promo.trim(), certificate_code: cert.trim() },
      })
        .then((q) => !cancelled && setQuote(q))
        .catch((err) => !cancelled && setQuoteError(err.message));
    }, 400);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [user, serviceId, date, time, promo, cert]);

  const service = services.find((s) => s.id === serviceId);

  const submit = async () => {
    setBookError("");
    setBooking(true);
    try {
      const body = { master: masterId, service: serviceId, date, start_time: time };
      if (promo.trim()) body.promo_code = promo.trim();
      if (cert.trim()) body.certificate_code = cert.trim();
      await api("/api/bookings/", { method: "POST", body });
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
  if (!shop) return (
    <>
      <div className="skeleton" style={{ marginTop: "1rem", minHeight: 260 }} />
      <div className="skeleton line" style={{ marginTop: "1rem" }} />
    </>
  );

  const [cover, ...restPhotos] = shop.photos || [];
  const discountLabel = quote?.discount_kind ? t(`price.${quote.discount_kind}`) : t("price.discount");

  return (
    <>
      <Link to="/" className="back">{t("back")}</Link>

      <div className="cover-hero">
        {cover ? <img src={cover.image} alt={shop.name} /> : <div className="ph">✂</div>}
        <div className="over">
          <h1>{shop.name}</h1>
          <p>📍 {[shop.city, shop.district, shop.address].filter(Boolean).join(", ")}</p>
        </div>
      </div>

      <div className="chips" style={{ marginTop: 0 }}>
        {shop.avg_rating != null && <span className="chip accent static">⭐ {shop.avg_rating} ({shop.reviews_count})</span>}
        <span className="chip static">🕘 {shop.opens_at?.slice(0, 5)} – {shop.closes_at?.slice(0, 5)}</span>
        {shop.phone && <a className="chip" href={`tel:${shop.phone}`}>📞 {shop.phone}</a>}
      </div>
      {shop.description && <p style={{ marginTop: ".9rem" }}>{shop.description}</p>}

      {restPhotos.length > 0 && (
        <div className="gallery" style={{ marginTop: "1rem" }}>
          {restPhotos.map((p) => <img key={p.id} src={p.image} alt={shop.name} loading="lazy" />)}
        </div>
      )}

      {loyalty && <div style={{ marginTop: "1rem" }}><Loyalty data={loyalty} t={t} /></div>}
      {offers.length > 0 && <Offers items={offers} t={t} />}

      <Step n={1} title={t("shop.step1").replace(/^\d+\.\s*/, "")} />
      <div className="cols">
        {services.map((s) => (
          <button key={s.id} className={`card option ${serviceId === s.id ? "active" : ""}`} onClick={() => setServiceId(s.id)}>
            <strong>{s.name}</strong>
            <span className="muted">{s.duration_minutes} {t("minutes")}</span>
            <span className="price">{money(s.price, t)}</span>
          </button>
        ))}
      </div>
      {services.length === 0 && <p className="muted">{t("shop.no_services")}</p>}

      <Step n={2} title={t("shop.step2").replace(/^\d+\.\s*/, "")} />
      <div className="cols">
        {masters.map((m) => (
          <button key={m.id} className={`card option ${masterId === m.id ? "active" : ""}`} onClick={() => setMasterId(m.id)}>
            <div className="opt-row">
              <div className="avatar">{m.photo ? <img src={m.photo} alt={m.name} /> : initials(m.name)}</div>
              <div className="grow">
                <strong>{m.name}</strong>
                <div className="muted">{m.avg_rating != null ? `⭐ ${m.avg_rating} (${m.reviews_count})` : t("shop.not_rated")}</div>
              </div>
            </div>
            {m.bio && <small className="muted">{m.bio}</small>}
          </button>
        ))}
      </div>
      {masters.length === 0 && <p className="muted">{t("shop.no_masters")}</p>}

      <Step n={3} title={t("shop.step3").replace(/^\d+\.\s*/, "")} />
      {!user ? (
        <div className="card">
          {t("shop.login_needed")}{" "}
          <Link to="/login" state={{ from: `/shop/${id}` }}>{t("shop.login_link")}</Link>.
        </div>
      ) : (
        <>
          <DatePicker value={date} onChange={setDate} lang={lang} />
          {!serviceId || !masterId ? (
            <p className="muted">{t("shop.pick_first")}</p>
          ) : slotsLoading ? (
            <p className="muted">{t("shop.searching")}</p>
          ) : slots.length === 0 ? (
            <div className="card">
              <p className="muted">{t("shop.no_slots")}</p>
              {waitlisted ? (
                <p className="ok">✅ {t("shop.waitlist_done")}</p>
              ) : (
                <button className="btn" onClick={joinWaitlist} disabled={booking}>
                  {booking ? t("wait") : `🔔 ${t("shop.waitlist")}`}
                </button>
              )}
            </div>
          ) : (
            <div className="slots">
              {slots.map((s) => (
                <button key={s} className={`slot ${time === s ? "active" : ""}`} onClick={() => setTime(s)}>{s}</button>
              ))}
            </div>
          )}

          {time && service && (
            <div className="card summary">
              <h3>{service.name} · {date} · {time}</h3>

              <div className="promo-row">
                <label className="muted">
                  <small>{t("shop.promo")}</small>
                  <input value={promo} onChange={(e) => setPromo(e.target.value)} placeholder={t("shop.promo_ph")} maxLength={30} />
                </label>
                <label className="muted">
                  <small>{t("shop.cert")}</small>
                  <input value={cert} onChange={(e) => setCert(e.target.value)} placeholder={t("shop.cert_ph")} maxLength={20} />
                </label>
              </div>

              <div className="price-lines">
                <div><span>{t("price.base")}</span><span>{money(quote?.base_price ?? service.price, t)}</span></div>
                {quote?.discount_amount > 0 && (
                  <div className="minus"><span>{discountLabel} (−{quote.discount_percent}%)</span><span>−{money(quote.discount_amount, t)}</span></div>
                )}
                {quote?.certificate_amount > 0 && (
                  <div className="minus"><span>{t("price.cert")}</span><span>−{money(quote.certificate_amount, t)}</span></div>
                )}
                <div className="total"><span>{t("price.total")}</span><span>{money(quote?.price ?? service.price, t)}</span></div>
              </div>
              {quote?.notes?.map((n) => <small key={n} className="muted">{n}</small>)}
              {quoteError && <p className="error">{quoteError}</p>}
              <small className="muted">{t("shop.pay_at_shop")}</small>

              {bookError && <p className="error">{bookError}</p>}
              <button className="btn block" onClick={submit} disabled={booking || !!quoteError}>
                {booking ? t("wait") : t("shop.book")}
              </button>
            </div>
          )}
          {!time && bookError && <p className="error">{bookError}</p>}
        </>
      )}

      {products.length > 0 && <Products items={products} user={user} shopId={id} t={t} />}

      {faq.length > 0 && (
        <>
          <h2>❓ {t("shop.faq")}</h2>
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

      <h2>💬 {t("shop.reviews")}</h2>
      {reviews.length === 0 && <p className="muted">{t("shop.no_reviews")}</p>}
      <div className="list">
        {reviews.map((r) => (
          <div key={r.id} className="card">
            <p><span className="stars">{stars(r.rating)}</span> <strong>{r.client_name}</strong></p>
            <p className="muted">{r.service} · {r.master_name}</p>
            {r.comment && <p>{r.comment}</p>}
          </div>
        ))}
      </div>
    </>
  );
}
