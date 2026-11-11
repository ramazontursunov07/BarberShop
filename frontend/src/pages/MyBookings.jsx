import { useCallback, useEffect, useState } from "react";
import { api, fetchAll } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { dateTime, money, todayISO } from "../format.js";

const ACTIVE = ["pending", "confirmed"];

function Reschedule({ booking, onDone, onClose }) {
  const { t } = useI18n();
  const [date, setDate] = useState(todayISO());
  const [slots, setSlots] = useState([]);
  const [time, setTime] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setTime("");
    setLoading(true);
    api("/api/bookings/slots/", { query: { master: booking.master, service: booking.service, date } })
      .then((d) => !cancelled && (setSlots(d.slots || []), setError("")))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [booking.master, booking.service, date]);

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await api(`/api/bookings/${booking.id}/reschedule/`, { method: "POST", body: { date, start_time: time } });
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <h3>{t("bk.reschedule_title")}</h3>
      <input type="date" className="search" value={date} min={todayISO()} onChange={(e) => setDate(e.target.value)} />
      {loading ? (
        <p className="muted">{t("shop.searching")}</p>
      ) : slots.length === 0 ? (
        <p className="muted">{t("shop.no_slots")}</p>
      ) : (
        <div className="slots">
          {slots.map((s) => (
            <button key={s} className={`slot ${time === s ? "active" : ""}`} onClick={() => setTime(s)}>
              {s}
            </button>
          ))}
        </div>
      )}
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button className="btn" disabled={!time || busy} onClick={submit}>
          {busy ? t("wait") : t("bk.confirm_move")}
        </button>
        <button className="link" onClick={onClose}>{t("bk.close")}</button>
      </div>
    </div>
  );
}

function ReviewForm({ booking, onDone, onClose }) {
  const { t } = useI18n();
  const [rating, setRating] = useState(5);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      await api("/api/reviews/", { method: "POST", body: { booking: booking.id, rating, comment } });
      onDone();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel">
      <h3>{t("bk.review_title")}</h3>
      <div className="stars big">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} className="star" onClick={() => setRating(n)} aria-label={`${n}`}>
            {n <= rating ? "★" : "☆"}
          </button>
        ))}
      </div>
      <textarea className="search" rows={3} maxLength={1000} placeholder={t("bk.comment")} value={comment} onChange={(e) => setComment(e.target.value)} />
      {error && <p className="error">{error}</p>}
      <div className="row">
        <button className="btn" disabled={busy} onClick={submit}>{busy ? t("wait") : t("bk.send")}</button>
        <button className="link" onClick={onClose}>{t("bk.close")}</button>
      </div>
    </div>
  );
}

function BookingCard({ b, reviewed, onChanged, onError }) {
  const { t, lang } = useI18n();
  const [panel, setPanel] = useState(null); // "move" | "review" | null
  const [busy, setBusy] = useState(false);
  const active = ACTIVE.includes(b.status);

  const cancel = async () => {
    if (!window.confirm(t("bk.cancel_confirm"))) return;
    setBusy(true);
    try {
      await api(`/api/bookings/${b.id}/cancel/`, { method: "POST" });
      onChanged();
    } catch (err) {
      onError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const done = () => {
    setPanel(null);
    onChanged();
  };

  return (
    <div className="card">
      <div className="booking">
        <div>
          <strong>{b.service_name}</strong>
          <p className="muted">{b.shop} · {t("bk.master")}: {b.master_name}</p>
          <p>{dateTime(b.start_time, lang)}</p>
          <p>{money(b.price, t)}</p>
        </div>
        <div className="right">
          <span className={`badge ${b.status}`}>{t(`status.${b.status}`)}</span>
          {active && (
            <>
              <button className="btn ghost" disabled={busy} onClick={() => setPanel(panel === "move" ? null : "move")}>
                {t("bk.reschedule")}
              </button>
              <button className="btn danger" disabled={busy} onClick={cancel}>{t("bk.cancel")}</button>
            </>
          )}
          {b.status === "completed" &&
            (reviewed ? (
              <span className="muted">{t("bk.reviewed")}</span>
            ) : (
              <button className="btn ghost" onClick={() => setPanel(panel === "review" ? null : "review")}>{t("bk.review")}</button>
            ))}
        </div>
      </div>
      {panel === "move" && <Reschedule booking={b} onDone={done} onClose={() => setPanel(null)} />}
      {panel === "review" && <ReviewForm booking={b} onDone={done} onClose={() => setPanel(null)} />}
    </div>
  );
}

export default function MyBookings() {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [reviewed, setReviewed] = useState(new Set());
  const [waitlist, setWaitlist] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [bookings, myReviews, wl] = await Promise.all([
        fetchAll("/api/bookings/"),
        fetchAll("/api/reviews/my/").catch(() => []),
        api("/api/bookings/waitlist/").catch(() => []),
      ]);
      setItems(bookings);
      setReviewed(new Set(myReviews.map((r) => r.booking)));
      setWaitlist(Array.isArray(wl) ? wl : []);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const leaveWaitlist = async (id) => {
    try {
      await api(`/api/bookings/waitlist/${id}/`, { method: "DELETE" });
      load();
    } catch (err) {
      setError(err.message);
    }
  };

  const upcoming = items.filter((b) => ACTIVE.includes(b.status));
  const past = items.filter((b) => !ACTIVE.includes(b.status));

  const renderCard = (b) => (
    <BookingCard key={b.id} b={b} reviewed={reviewed.has(b.id)} onChanged={load} onError={setError} />
  );

  return (
    <>
      <h1>{t("bk.title")}</h1>
      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">{t("loading")}</p>}
      {!loading && items.length === 0 && <p className="muted">{t("bk.empty")}</p>}

      {upcoming.length > 0 && <h2>{t("bk.upcoming")}</h2>}
      <div className="list">{upcoming.map(renderCard)}</div>

      {waitlist.length > 0 && (
        <>
          <h2>{t("bk.waitlist")}</h2>
          <div className="list">
            {waitlist.map((w) => (
              <div key={w.id} className="card booking">
                <div>
                  <strong>{w.service_name}</strong>
                  <p className="muted">{w.shop} · {w.date}{w.from_time ? ` ${w.from_time.slice(0, 5)}–${(w.to_time || "").slice(0, 5)}` : ""}</p>
                </div>
                <button className="btn danger" onClick={() => leaveWaitlist(w.id)}>{t("bk.leave")}</button>
              </div>
            ))}
          </div>
        </>
      )}

      {past.length > 0 && <h2>{t("bk.history")}</h2>}
      <div className="list">{past.map(renderCard)}</div>
    </>
  );
}
