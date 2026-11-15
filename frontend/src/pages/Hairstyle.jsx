import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import Icon from "../components/Icon.jsx";
import { useToast } from "../components/Toast.jsx";

export default function Hairstyle() {
  const { user } = useAuth();
  const { t } = useI18n();
  const { toast } = useToast();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const input = useRef(null);

  const pick = (e) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    setRes(null);
    setPreview(URL.createObjectURL(f));
  };

  const analyze = async () => {
    if (!file) return;
    const fd = new FormData();
    fd.append("photo", file);
    setBusy(true);
    try {
      setRes(await api("/api/insights/hairstyle/", { method: "POST", body: fd }));
    } catch (err) {
      toast(err.message, "err");
    } finally {
      setBusy(false);
    }
  };

  if (!user) {
    return (
      <div className="empty card" style={{ marginTop: "2rem" }}>
        <Icon name="camera" size={44} stroke={1.4} />
        <h2>{t("style.title")}</h2>
        <p>{t("ai.login")}</p>
        <Link className="btn" to="/login" state={{ from: "/hairstyle" }}>{t("login.submit")}</Link>
      </div>
    );
  }

  return (
    <>
      <h1><Icon name="camera" size={24} style={{ verticalAlign: "-4px", color: "var(--accent)" }} /> {t("style.title")}</h1>
      <p className="muted">{t("style.sub")}</p>

      <input ref={input} type="file" accept="image/*" capture="user" hidden onChange={pick} />
      {preview ? <img src={preview} alt="" className="preview" /> : (
        <div className="drop" onClick={() => input.current?.click()}>
          <Icon name="camera" size={40} stroke={1.4} /><p>{t("style.pick")}</p>
        </div>
      )}
      <div className="row">
        {preview && <button className="btn ghost" onClick={() => input.current?.click()}>{t("style.change")}</button>}
        {file && <button className="btn" onClick={analyze} disabled={busy}>{busy ? t("style.analyzing") : t("style.go")}</button>}
      </div>

      {res && (
        <div className="list" style={{ marginTop: "1rem" }}>
          <div className="card">
            <span className="chip gold">{t("style.shape")}</span>
            <h2 style={{ margin: ".4rem 0" }}>{res.face_shape_name}</h2>
            <div className="progress"><div style={{ width: `${Math.round((res.confidence || 0) * 100)}%` }} /></div>
            <small className="muted">{Math.round((res.confidence || 0) * 100)}%</small>
            {res.note && <p className="muted">{res.note}</p>}
          </div>
          {res.hairstyles?.map((h) => (
            <div key={h.name} className="card"><strong>✂ {h.name}</strong><p className="muted">{h.why}</p></div>
          ))}
          {res.avoid && <div className="card"><strong>{t("style.avoid")}</strong><p className="muted">{Array.isArray(res.avoid) ? res.avoid.join(", ") : res.avoid}</p></div>}
          <Link className="btn" to="/" style={{ textAlign: "center" }}>{t("style.book")}</Link>
        </div>
      )}
    </>
  );
}
