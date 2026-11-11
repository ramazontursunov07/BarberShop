import { useCallback, useEffect, useState } from "react";
import { api, results } from "../api.js";
import { STATUS, dateTime, money } from "../format.js";

const ACTIVE = ["pending", "confirmed"];

export default function MyBookings() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try {
      setItems(results(await api("/api/bookings/")));
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

  const cancel = async (b) => {
    if (!window.confirm("Bronni bekor qilasizmi?")) return;
    setBusyId(b.id);
    setError("");
    try {
      await api(`/api/bookings/${b.id}/cancel/`, { method: "POST" });
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  const active = items.filter((b) => ACTIVE.includes(b.status));
  const past = items.filter((b) => !ACTIVE.includes(b.status));

  const Row = (b) => (
    <div key={b.id} className="card booking">
      <div>
        <strong>{b.service_name}</strong>
        <p className="muted">{b.shop} · usta: {b.master_name}</p>
        <p>{dateTime(b.start_time)}</p>
        <p>{money(b.price)}</p>
      </div>
      <div className="right">
        <span className={`badge ${b.status}`}>{STATUS[b.status] || b.status}</span>
        {ACTIVE.includes(b.status) && (
          <button className="btn danger" disabled={busyId === b.id} onClick={() => cancel(b)}>
            Bekor qilish
          </button>
        )}
      </div>
    </div>
  );

  return (
    <>
      <h1>Bronlarim</h1>
      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Yuklanmoqda...</p>}
      {!loading && items.length === 0 && <p className="muted">Hali bronlaringiz yo'q.</p>}

      {active.length > 0 && <h2>Kelgusi bronlar</h2>}
      <div className="list">{active.map(Row)}</div>

      {past.length > 0 && <h2>Tarix</h2>}
      <div className="list">{past.map(Row)}</div>
    </>
  );
}
