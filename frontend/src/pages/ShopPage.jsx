import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, results } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { dayChip, isOpenNow, mapsLink, money, partOfDay, shiftDate, todayISO } from "../format.js";
import Icon from "../components/Icon.jsx";
import { Avatar, Skeleton } from "../components/ui.jsx";
import { useToast } from "../components/Toast.jsx";

const MAX_SERVICES = 4; // asosiy + 3 ta qo'shimcha (backend chegarasi)
const stars = (n) => "★".repeat(n) + "☆".repeat(5 - n);
const PARTS = [["morning", "sun"], ["day", "bolt"], ["evening", "moon"]];

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
  const { toast } = useToast();
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
  const [photo, setPhoto] = useState(0);

  const [picked, setPicked] = useState([]); // xizmat id lari (tanlangan tartibda)
  const [masterId, setMasterId] = useState(null);
  const [date, setDate] = useState(todayISO());
  const [slots, setSlots] = useState([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [time, setTime] = useState("");

  const [promoInput, setPromoInput] = useState("");
  const [certInput, setCertInput] = useState("");
  const [applied, setApplied] = useState({ promo: "", cert: "" });
  const [quote, setQuote] = useState(null);
  const [quoteError, setQuoteError] = useState("");

  const [booking, setBooking] = useState(false);
  const [bookError, setBookError] = useState("");
  const [waitlisted, setWaitlisted] = useState(false);
  const [done, setDone] = useState(null);

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

  useEffect(() => {
    if (!user) return setLoyalty(null);
    api("/api/promotions/loyalty/", { query: { shop: id } }).then(setLoyalty).catch(() => setLoyalty(null));
  }, [user, id]);

  const chosen = useMemo(() => picked.map((sid) => services.find((s) => s.id === sid)).filter(Boolean), [picked, services]);
  const primary = chosen[0];
  const extras = chosen.slice(1).map((s) => s.id);
  const totalMin = chosen.reduce((a, s) => a + (s.duration_minutes || 0), 0);
  const totalBase = chosen.reduce((a, s) => a + Number(s.price || 0), 0);

  const toggleService = (sid) =>
    setPicked((list) => {
      if (list.includes(sid)) return list.filter((x) => x !== sid);
      if (list.length >= MAX_SERVICES) {
        toast(t("shop.max_services", { n: MAX_SERVICES }), "err");
        return list;
      }
      return [...list, sid];
    });

  // Bo'sh vaqtlar: xizmatlar (qo'shimchalar bilan), usta va sana o'zgarganda
  useEffect(() => {
    setTime("");
    setSlots([]);
    setWaitlisted(false);
    setBookError("");
    if (!user || !primary || !masterId || !date) return;
    let cancelled = false;
    setSlotsLoading(true);
    api("/api/bookings/slots/", {
      query: { master: masterId, service: primary.id, date, ...(extras.length ? { extra_services: extras.join(",") } : {}) },
    })
      .then((data) => !cancelled && setSlots(data.slots || []))
      .catch((err) => !cancelled && setBookError(err.message))
      .finally(() => !cancelled && setSlotsLoading(false));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, picked.join(","), masterId, date]);

  // Aniq narx: chegirma, promokod, sertifikat (vaqt tanlangach)
  useEffect(() => {
    setQuote(null);
    setQuoteError("");
    if (!user || !primary || !time) return;
    let cancelled = false;
    api("/api/promotions/quote/", {
      method: "POST",
      body: { service: primary.id, date, start_time: time, promo_code: applied.promo, certificate_code: applied.cert, extra_services: extras },
    })
      .then((q) => !cancelled && setQuote(q))
      .catch((err) => !cancelled && setQuoteError(err.message));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, picked.join(","), date, time, applied.promo, applied.cert]);

  const applyCodes = () => setApplied({ promo: promoInput.trim().toUpperCase(), cert: certInput.trim().toUpperCase() });

  const submit = async () => {
    setBookError("");
    setBooking(true);
    try {
      await api("/api/bookings/", {
        method: "POST",
        body: { master: masterId, service: primary.id, date, start_time: time, promo_code: applied.promo, certificate_code: applied.cert, extra_services: extras },
      });
      setDone({ names: chosen.map((s) => s.name).join(" + "), date, time, price: quote?.price ?? totalBase, master: masters.find((m) => m.id === masterId)?.name });
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setBookError(err.message);
      toast(err.message, "err");
    } finally {
      setBooking(false);
    }
  };

  const joinWaitlist = async () => {
    setBooking(true);
    try {
      await api("/api/bookings/waitlist/", { method: "POST", body: { service: primary.id, master: masterId, date } });
      setWaitlisted(true);
      toast(t("shop.waitlist_done"));
    } catch (err) {
      toast(err.message, "err");
    } finally {
      setBooking(false);
    }
  };

  if (loadError) return <p className="error" style={{ marginTop: "2rem" }}>{loadError}</p>;
  if (!shop) {
    return (
      <div style={{ marginTop: "1rem", display: "grid", gap: ".8rem" }}>
        <Skeleton h={220} /><Skeleton h={26} w="60%" /><Skeleton h={90} /><Skeleton h={90} />
      </div>
    );
  }

  if (done) {
    return (
      <div className="success card" style={{ marginTop: "1.5rem" }}>
        <div className="tick"><Icon name="check" size={42} stroke={2.6} /></div>
        <h1 style={{ marginTop: 0 }}>{t("shop.done_title")}</h1>
        <p><strong>{done.names}</strong></p>
        <p className="muted">{done.master} · {done.date} · {done.time}</p>
        <p style={{ fontSize: "1.2rem", fontWeight: 800 }}>{money(done.price, t)}</p>
        <p className="muted">{t("shop.done_hint")}</p>
        <div className="row" style={{ justifyContent: "center" }}>
          <button className="btn" onClick={() => navigate("/bookings")}>{t("nav.bookings")}</button>
          <button className="btn ghost" onClick={() => navigate("/")}>{t("nav.home")}</button>
        </div>
      </div>
    );
  }

  const open = isOpenNow(shop.opens_at, shop.closes_at);
  const photos = shop.photos || [];
  const days = Array.from({ length: 14 }, (_, i) => dayChip(shiftDate(todayISO(), i), lang));
  const grouped = PARTS.map(([key, icon]) => [key, icon, slots.filter((s) => partOfDay(s) === key)]).filter(([, , list]) => list.length);
  const finalPrice = quote?.price ?? totalBase;
  const canBook = user && primary && masterId && time;

  return (
    <>
      <Link to="/" className="back">{t("back")}</Link>

      <div className="shop-hero">
        {photos[photo] && <img src={photos[photo].image} alt={shop.name} />}
        {!photos[photo] && <div style={{ display: "grid", placeItems: "center", height: "100%", color: "var(--muted)" }}><Icon name="scissors" size={56} stroke={1.2} /></div>}
        <div className="over"><h1>{shop.name}</h1></div>
      </div>
      {photos.length > 1 && (
        <div className="thumbs">
          {photos.map((p, i) => <img key={p.id} src={p.image} alt="" className={i === photo ? "on" : ""} onClick={() => setPhoto(i)} loading="lazy" />)}
        </div>
      )}

      <div className="info-row">
        {open != null && <span className={`chip ${open ? "ok" : "off"}`}>{open ? t("home.open") : t("home.closed")}</span>}
        <span className="chip"><Icon name="clock" size={14} /> {shop.opens_at?.slice(0, 5)} – {shop.closes_at?.slice(0, 5)}</span>
        {shop.avg_rating != null && <span className="chip gold"><Icon name="star" size={13} fill="currentColor" /> {shop.avg_rating} ({shop.reviews_count})</span>}
        <a className="chip" href={mapsLink(shop.latitude, shop.longitude, `${shop.city} ${shop.address}`)} target="_blank" rel="noreferrer">
          <Icon name="pin" size={14} /> {[shop.city, shop.district, shop.address].filter(Boolean).join(", ")}
        </a>
        {shop.phone && <a className="chip" href={`tel:${shop.phone}`}><Icon name="phone" size={14} /> {shop.phone}</a>}
      </div>
      {shop.description && <p style={{ marginTop: ".8rem" }}>{shop.description}</p>}

      {loyalty && (
        <div className="card loyalty" style={{ marginTop: "1rem" }}>
          <div className="row" style={{ justifyContent: "space-between", margin: 0 }}>
            <strong><Icon name="gift" size={17} style={{ verticalAlign: "-3px" }} /> {t("shop.loyalty")}</strong>
            <span className="chip gold">−{loyalty.discount_percent}%</span>
          </div>
          <div className="progress"><div style={{ width: `${loyalty.reward_available ? 100 : ((loyalty.every_n_visits - loyalty.visits_to_next_reward) / loyalty.every_n_visits) * 100}%` }} /></div>
          <small className="muted">
            {loyalty.reward_available ? t("shop.loyalty_ready", { p: loyalty.discount_percent }) : t("shop.loyalty_left", { n: loyalty.visits_to_next_reward, p: loyalty.discount_percent })}
          </small>
        </div>
      )}

      {offers.length > 0 && (
        <>
          <h2>{t("shop.offers")}</h2>
          <div className="near-row">
            {offers.map((o) => (
              <button key={o.code} className="card offer" style={{ textAlign: "left", font: "inherit", color: "var(--text)", cursor: "pointer" }}
                onClick={() => { setPromoInput(o.code); toast(t("shop.promo_copied", { c: o.code })); }}>
                <code>{o.code}</code>
                <p><strong>{o.percent ? `−${o.percent}%` : `−${money(o.amount, t)}`}</strong></p>
                <small className="muted">{o.description}</small>
              </button>
            ))}
          </div>
        </>
      )}

      <div className="steps"><span className="n">1</span>{t("shop.step1")}</div>
      <p className="muted" style={{ marginTop: 0 }}>{t("shop.multi_hint")}</p>
      <div className="list">
        {services.map((s) => {
          const on = picked.includes(s.id);
          return (
            <button key={s.id} className={`card svc ${on ? "active" : ""}`} onClick={() => toggleService(s.id)} aria-pressed={on}>
              <span className="check"><Icon name="check" size={15} stroke={3} /></span>
              <span className="grow"><strong>{s.name}</strong><br /><small className="muted">{s.duration_minutes} {t("minutes")}</small></span>
              <span className="price">{money(s.price, t)}</span>
            </button>
          );
        })}
        {services.length === 0 && <p className="muted">{t("shop.no_services")}</p>}
      </div>

      <div className="steps"><span className="n">2</span>{t("shop.step2")}</div>
      <div className="masters">
        {masters.map((m) => (
          <button key={m.id} className={`card master ${masterId === m.id ? "active" : ""}`} onClick={() => setMasterId(m.id)}>
            <Avatar name={m.name} />
            <strong>{m.name}</strong>
            <small className="muted">{m.avg_rating != null ? `★ ${m.avg_rating} (${m.reviews_count})` : t("shop.not_rated")}</small>
            {m.bio && <small className="muted">{m.bio}</small>}
          </button>
        ))}
        {masters.length === 0 && <p className="muted">{t("shop.no_masters")}</p>}
      </div>

      <div className="steps"><span className="n">3</span>{t("shop.step3")}</div>
      {!user ? (
        <div className="card">
          {t("shop.login_needed")}{" "}
          <Link to="/login" state={{ from: `/shop/${id}` }}>{t("shop.login_link")}</Link>.
        </div>
      ) : (
        <>
          <div className="dates">
            {days.map((d) => (
              <button key={d.iso} className={`date ${date === d.iso ? "active" : ""}`} onClick={() => setDate(d.iso)}>
                <small>{d.dow}</small><strong>{d.day}</strong>
              </button>
            ))}
          </div>

          {!primary || !masterId ? (
            <p className="muted" style={{ marginTop: ".8rem" }}>{t("shop.pick_first")}</p>
          ) : slotsLoading ? (
            <div className="slots" style={{ marginTop: ".8rem" }}>{Array.from({ length: 8 }, (_, i) => <Skeleton key={i} h={42} />)}</div>
          ) : slots.length === 0 ? (
            <div className="card" style={{ marginTop: ".8rem" }}>
              <p className="muted">{t("shop.no_slots")}</p>
              {waitlisted ? <p className="ok">✓ {t("shop.waitlist_done")}</p> : (
                <button className="btn ghost" onClick={joinWaitlist} disabled={booking}>{booking ? t("wait") : t("shop.waitlist")}</button>
              )}
            </div>
          ) : (
            grouped.map(([key, icon, list]) => (
              <div key={key}>
                <div className="part"><Icon name={icon} size={15} /> {t(`part.${key}`)}</div>
                <div className="slots">
                  {list.map((s) => <button key={s} className={`slot ${time === s ? "active" : ""}`} onClick={() => setTime(s)}>{s}</button>)}
                </div>
              </div>
            ))
          )}

          {time && primary && (
            <div className="card summary">
              <h3>{t("shop.summary")}</h3>
              <div className="promo" style={{ margin: ".6rem 0" }}>
                <input placeholder={t("shop.promo")} value={promoInput} onChange={(e) => setPromoInput(e.target.value)} />
                <input placeholder={t("shop.cert")} value={certInput} onChange={(e) => setCertInput(e.target.value)} />
                <button className="btn ghost" onClick={applyCodes}>{t("shop.apply")}</button>
              </div>
              <div className="price-lines">
                {chosen.map((s) => <div key={s.id}><span>{s.name}</span><span>{money(s.price, t)}</span></div>)}
                {quote && quote.discount_amount > 0 && (
                  <div className="disc"><span>{t("shop.discount")} {quote.discount_percent ? `(−${quote.discount_percent}%)` : ""}</span><span>−{money(quote.discount_amount, t)}</span></div>
                )}
                {quote && quote.certificate_amount > 0 && (
                  <div className="disc"><span>{t("shop.cert")}</span><span>−{money(quote.certificate_amount, t)}</span></div>
                )}
                <div className="total"><span>{t("shop.price")}</span><span>{money(finalPrice, t)}</span></div>
              </div>
              {quote?.notes?.map((n) => <p key={n} className="muted"><small>{n}</small></p>)}
              {quoteError && <p className="error">{quoteError}</p>}
              {bookError && <p className="error">{bookError}</p>}
            </div>
          )}
        </>
      )}

      {shop && faq.length > 0 && (
        <>
          <h2>{t("shop.faq")}</h2>
          <div className="list">
            {faq.map((f) => (
              <details key={f.id} className="card"><summary>{f.question}</summary><p className="muted">{f.answer}</p></details>
            ))}
          </div>
        </>
      )}

      {products.length > 0 && <Products items={products} user={user} shopId={id} t={t} />}

      <h2>{t("shop.reviews")}</h2>
      {reviews.length === 0 && <p className="muted">{t("shop.no_reviews")}</p>}
      <div className="list">
        {reviews.map((r) => (
          <div key={r.id} className="card">
            <div className="row" style={{ margin: 0 }}>
              <Avatar name={r.client_name || "?"} small />
              <div className="grow"><strong>{r.client_name}</strong><br /><span className="stars">{stars(r.rating)}</span></div>
            </div>
            <p className="muted">{r.service} · {r.master_name}</p>
            {r.comment && <p>{r.comment}</p>}
          </div>
        ))}
      </div>

      {(primary || canBook) && (
        <div className="cta-bar">
          <div className="cta-in">
            <div className="tot">
              <small>{chosen.length} {t("shop.services_n")} · {totalMin} {t("minutes")}</small>
              <strong>{money(finalPrice, t)}</strong>
            </div>
            {!user ? (
              <button className="btn" onClick={() => navigate("/login", { state: { from: `/shop/${id}` } })}>{t("shop.login_link")}</button>
            ) : (
              <button className="btn" onClick={submit} disabled={!canBook || booking}>
                {booking ? t("wait") : canBook ? t("shop.book") : !masterId ? t("shop.cta_master") : t("shop.cta_time")}
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}
