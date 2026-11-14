import { useCallback, useEffect, useState } from "react";
import { api } from "../../api.js";
import { useI18n } from "../../i18n.jsx";
import PaymentButtons from "./PaymentButtons.jsx";

const POLL_MS = 15000;

export default function QueueTab({ me }) {
  const { t } = useI18n();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [payFor, setPayFor] = useState(null);

  const load = useCallback(async () => {
    try {
      setItems(await api("/api/bookings/queue/staff/", { query: { shop: me.shop_id } }));
      setError("");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [me.shop_id]);

  useEffect(() => {
    load();
    const id = setInterval(load, POLL_MS); // yangi kelganlarni o'zi ko'rsatadi
    return () => clearInterval(id);
  }, [load]);

  const run = async (fn) => {
    setBusy(true);
    setError("");
    try {
      await fn();
      setPayFor(null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  const callNext = () => run(() => api("/api/bookings/queue/call-next/", { method: "POST", body: { master: me.id } }));
  const finish = (id, payment_method) =>
    run(() => api(`/api/bookings/queue/${id}/finish/`, { method: "POST", body: { payment_method } }));

  const waiting = items.filter((x) => x.status === "waiting");
  const serving = items.filter((x) => x.status === "serving");

  return (
    <>
      <div className="row">
        <h2 style={{ margin: 0 }} className="grow">{t("q.title")}</h2>
        <button className="btn ghost" onClick={load}>{t("q.refresh")}</button>
      </div>
      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">{t("loading")}</p>}
      {!loading && items.length === 0 && <p className="muted">{t("q.empty")}</p>}

      {serving.map((x) => (
        <div key={x.id} className="card" style={{ borderColor: "var(--ok)" }}>
          <div className="booking">
            <div>
              <span className="badge completed">{t("q.serving")}</span>
              <h3>{x.client} · <a href={`tel:${x.phone}`}>{x.phone}</a></h3>
              <p className="muted">{x.service}{x.master ? ` · ${x.master}` : ""}</p>
            </div>
            {x.master === me.name && payFor !== x.id && (
              <button className="btn" disabled={busy} onClick={() => setPayFor(x.id)}>{t("q.finish")}</button>
            )}
          </div>
          {payFor === x.id && <PaymentButtons disabled={busy} onPick={(m) => finish(x.id, m)} onCancel={() => setPayFor(null)} />}
        </div>
      ))}

      {waiting.length > 0 && (
        <button className="btn" disabled={busy || !me.is_active} onClick={callNext}>{t("q.next")}</button>
      )}

      <div className="list" style={{ marginTop: ".8rem" }}>
        {waiting.map((x) => (
          <div key={x.id} className="card booking">
            <div>
              <strong>#{x.position}</strong> · {x.client} · <a href={`tel:${x.phone}`}>{x.phone}</a>
              <p className="muted">{x.service}{x.master ? ` · ${x.master}` : ""}</p>
            </div>
            <span className="muted">{t("q.wait", { n: x.estimated_wait_minutes })}</span>
          </div>
        ))}
      </div>
    </>
  );
}
