import { useCallback, useEffect, useState } from "react";
import { api, fetchAll } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import { money, shiftDate, timeOnly, todayISO } from "../../format.js";
import PaymentButtons from "../master/PaymentButtons.jsx";

// Joriy holatdan keyin mumkin bo'lgan harakatlar (backend TRANSITIONS bilan bir xil)
const ACTIONS = {
  pending: ["confirmed", "cancelled"],
  confirmed: ["completed", "no_show", "cancelled"],
};

export default function BookingsTab({ shopName }) {
  const { t } = useI18n();
  const [date, setDate] = useState(todayISO());
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [payFor, setPayFor] = useState(null); // "Bajarildi" bosilgan bron: to'lov usuli so'raladi

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await fetchAll("/api/bookings/shop/", { date });
      setItems(shopName ? list.filter((b) => b.shop === shopName) : list);
      setError("");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [date, shopName]);

  useEffect(() => {
    load();
  }, [load]);

  const act = async (b, status, payment_method = "") => {
    if (status === "cancelled" && !window.confirm(t("bk.cancel_confirm"))) return;
    if (status === "completed" && !payment_method) {
      setPayFor(b.id);
      return;
    }
    setBusyId(b.id);
    setError("");
    try {
      await api(`/api/bookings/${b.id}/status/`, {
        method: "POST",
        body: payment_method ? { status, payment_method } : { status },
      });
      setPayFor(null);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  return (
    <>
      <div className="row">
        <button className="btn ghost" onClick={() => setDate(shiftDate(date, -1))}>‹</button>
        <input type="date" className="search grow" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} />
        <button className="btn ghost" onClick={() => setDate(shiftDate(date, 1))}>›</button>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">{t("loading")}</p>}
      {!loading && items.length === 0 && <p className="muted">{t("own.no_bookings")}</p>}
      {items.length > 0 && <p className="muted">{t("own.total")}: {items.length}</p>}

      <div className="list">
        {items.map((b) => (
          <div key={b.id} className="card booking">
            <div>
              <strong>{timeOnly(b.start_time)}–{timeOnly(b.end_time)}</strong> · {b.service_name}
              <p>{b.client_name} · <a href={`tel:${b.client_phone}`}>{b.client_phone}</a></p>
              <p className="muted">{b.master_name} · {money(b.price, t)}</p>
            </div>
            <div className="right">
              <span className={`badge ${b.status}`}>{t(`status.${b.status}`)}</span>
              {(ACTIONS[b.status] || []).map((s) => (
                <button
                  key={s}
                  className={`btn ${s === "cancelled" || s === "no_show" ? "danger" : "ghost"}`}
                  disabled={busyId === b.id}
                  onClick={() => act(b, s)}
                >
                  {t(`own.act.${s}`)}
                </button>
              ))}
            </div>
            {payFor === b.id && (
              <PaymentButtons disabled={busyId === b.id} onPick={(m) => act(b, "completed", m)} onCancel={() => setPayFor(null)} />
            )}
          </div>
        ))}
      </div>
    </>
  );
}
