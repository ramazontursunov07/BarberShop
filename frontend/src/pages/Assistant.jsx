import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { speak, stopSpeaking } from "../speech.js";
import { useI18n } from "../i18n.jsx";
import Icon from "../components/Icon.jsx";
import { useToast } from "../components/Toast.jsx";

export default function Assistant() {
  const { user } = useAuth();
  const { t, lang } = useI18n();
  const { toast } = useToast();
  const [msgs, setMsgs] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem("ai_chat") || "[]"); } catch { return []; }
  });
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState(false);
  const [autoVoice, setAutoVoice] = useState(() => {
    try { return localStorage.getItem("ai_voice") === "1"; } catch { return false; }
  });
  const [speakingIdx, setSpeakingIdx] = useState(-1);
  const recorder = useRef(null);
  const endRef = useRef(null);
  const msgsRef = useRef(msgs); // mikrofon yozuvi tugagach chaqiriladigan send eski holatni ko'rmasligi uchun
  msgsRef.current = msgs;
  const autoRef = useRef(autoVoice);
  autoRef.current = autoVoice;

  useEffect(() => stopSpeaking, []); // sahifadan chiqqanda ovoz to'xtaydi

  const readAloud = async (text, idx) => {
    if (speakingIdx === idx) {
      stopSpeaking();
      setSpeakingIdx(-1);
      return;
    }
    setSpeakingIdx(idx);
    try {
      await speak(text, lang, () => setSpeakingIdx((cur) => (cur === idx ? -1 : cur)));
    } catch (err) {
      setSpeakingIdx(-1);
      toast(err.message === "no_voice" ? t("ai.no_voice") : err.name === "NotAllowedError" ? t("ai.tap_to_play") : err.message, "err");
    }
  };

  const toggleAutoVoice = () => {
    const next = !autoVoice;
    setAutoVoice(next);
    try { localStorage.setItem("ai_voice", next ? "1" : "0"); } catch { /* ignore */ }
    if (!next) { stopSpeaking(); setSpeakingIdx(-1); }
  };

  useEffect(() => {
    try { sessionStorage.setItem("ai_chat", JSON.stringify(msgs.slice(-30))); } catch { /* ignore */ }
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs, busy]);

  const send = async (raw, fromVoice = false) => {
    const message = (raw ?? text).trim();
    if (!message || busy) return;
    const current = msgsRef.current;
    const history = current.map((m) => ({ role: m.role, content: m.content }));
    setMsgs((l) => [...l, { role: "user", content: message }]);
    setText("");
    setBusy(true);
    try {
      const data = await api("/api/ai/chat/", { method: "POST", body: { message, history } });
      const replyIndex = current.length + 1; // foydalanuvchi xabaridan keyingi o'rin
      setMsgs((l) => [...l, { role: "assistant", content: data.reply }]);
      if (autoRef.current || fromVoice) setTimeout(() => readAloud(data.reply, replyIndex), 0); // ovozli savolga ovozli javob
    } catch (err) {
      toast(err.message, "err");
      setMsgs((l) => l.slice(0, -1));
      setText(message);
    } finally {
      setBusy(false);
    }
  };

  const toggleMic = async () => {
    if (rec) {
      recorder.current?.stop();
      return;
    }
    stopSpeaking(); // gapirayotganda AI jim turadi
    setSpeakingIdx(-1);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") return toast(t("ai.no_mic"), "err");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      const mr = new MediaRecorder(stream);
      mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      mr.onstop = async () => {
        stream.getTracks().forEach((tr) => tr.stop());
        setRec(false);
        const blob = new Blob(chunks, { type: mr.mimeType || "audio/webm" });
        if (!blob.size) return;
        const fd = new FormData();
        const ext = (mr.mimeType || "").includes("mp4") ? "m4a" : "webm";
        fd.append("audio", blob, `voice.${ext}`);
        setBusy(true);
        try {
          const data = await api("/api/ai/transcribe/", { method: "POST", body: fd });
          setBusy(false);
          if (data.text) send(data.text, true);
        } catch (err) {
          setBusy(false);
          toast(err.message, "err");
        }
      };
      recorder.current = mr;
      mr.start();
      setRec(true);
      setTimeout(() => mr.state === "recording" && mr.stop(), 60000);
    } catch {
      toast(t("ai.no_mic"), "err");
    }
  };

  if (!user) {
    return (
      <div className="empty card" style={{ marginTop: "2rem" }}>
        <Icon name="sparkle" size={44} stroke={1.4} />
        <h2>{t("ai.title")}</h2>
        <p>{t("ai.login")}</p>
        <Link className="btn" to="/login" state={{ from: "/assistant" }}>{t("login.submit")}</Link>
      </div>
    );
  }

  const ideas = [t("ai.i1"), t("ai.i2"), t("ai.i3"), t("ai.i4")];

  return (
    <div className="chat">
      <div className="row" style={{ justifyContent: "space-between", margin: ".5rem 0 0" }}>
        <h1 style={{ margin: 0 }}><Icon name="sparkle" size={22} style={{ verticalAlign: "-3px", color: "var(--accent)" }} /> {t("ai.title")}</h1>
        <div className="row" style={{ margin: 0 }}>
          <button className="icon-btn" onClick={toggleAutoVoice} aria-pressed={autoVoice}
            title={autoVoice ? t("ai.voice_on") : t("ai.voice_off")} aria-label={t("ai.voice_off")}
            style={autoVoice ? { background: "var(--accent)", borderColor: "var(--accent)", color: "var(--on-accent)" } : undefined}>
            <Icon name={autoVoice ? "volume" : "mute"} size={18} />
          </button>
          {msgs.length > 0 && <button className="link" onClick={() => { stopSpeaking(); setSpeakingIdx(-1); setMsgs([]); }}>{t("ai.clear")}</button>}
        </div>
      </div>
      <div className="msgs">
        {msgs.length === 0 && (
          <div className="card" style={{ marginTop: ".6rem" }}>
            <p>{t("ai.hello")}</p>
            <div className="suggest" style={{ flexWrap: "wrap" }}>
              {ideas.map((i) => <button key={i} className="tab" onClick={() => send(i)}>{i}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => (
          <div key={i} className={`msg ${m.role === "user" ? "me" : "bot"}`}>
            {m.content.replace(/\*\*/g, "")}
            {m.role !== "user" && (
              <button className="icon-btn" onClick={() => readAloud(m.content, i)} aria-label={t("ai.listen")} title={t("ai.listen")}
                style={{ width: 30, height: 30, marginLeft: ".5rem", verticalAlign: "middle", display: "inline-grid" }}>
                <Icon name={speakingIdx === i ? "stop" : "volume"} size={15} />
              </button>
            )}
          </div>
        ))}
        {busy && <div className="msg bot"><span className="typing"><i /><i /><i /></span></div>}
        <div ref={endRef} />
      </div>
      <div className="composer">
        <button className={`icon-btn ${rec ? "rec" : ""}`} onClick={toggleMic} aria-label="mic" disabled={busy && !rec}>
          <Icon name="mic" size={20} />
        </button>
        <textarea rows={1} value={text} placeholder={rec ? t("ai.listening") : t("ai.placeholder")} maxLength={1000}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }} />
        <button className="icon-btn send" onClick={() => send()} disabled={busy || !text.trim()} aria-label="send">
          <Icon name="send" size={20} />
        </button>
      </div>
    </div>
  );
}
