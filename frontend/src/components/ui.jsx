import { useEffect, useState } from "react";
import Icon from "./Icon.jsx";

export const Skeleton = ({ h = 16, w = "100%", className = "" }) => (
  <div className={`skel ${className}`} style={{ height: h, width: w }} />
);

export const ShopSkeletons = ({ n = 6 }) => (
  <div className="shop-grid">
    {Array.from({ length: n }, (_, i) => (
      <div key={i} className="skel skel-card" />
    ))}
  </div>
);

export function Sheet({ title, onClose, children }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="sheet-back" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="row" style={{ justifyContent: "space-between", marginTop: 0 }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="close"><Icon name="close" size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export const Empty = ({ icon = "scissors", children }) => (
  <div className="empty"><Icon name={icon} size={44} stroke={1.4} /><p>{children}</p></div>
);

export const Avatar = ({ name = "?", small }) => (
  <div className={`avatar ${small ? "sm" : ""}`}>{(name.trim()[0] || "?").toUpperCase()}</div>
);

// Parol maydoni: ko'z tugmasi bilan parolni ko'rsatadi/yashiradi
export function PasswordInput({ label_show = "Show", label_hide = "Hide", ...props }) {
  const [shown, setShown] = useState(false);
  return (
    <div className="pw-wrap">
      <input {...props} type={shown ? "text" : "password"} />
      <button type="button" className="pw-toggle" onClick={() => setShown((v) => !v)}
        aria-label={shown ? label_hide : label_show} title={shown ? label_hide : label_show}>
        <Icon name={shown ? "eyeoff" : "eye"} size={18} />
      </button>
    </div>
  );
}
