import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { LANG_LIST } from "../locales.js";

function useTheme() {
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute("data-theme") || "dark");
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("theme", next);
    } catch {
      /* private rejim: tanlov saqlanmaydi */
    }
    setTheme(next);
  };
  return [theme, toggle];
}

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [theme, toggleTheme] = useTheme();
  const role = user?.role;

  const panel = role === "owner" ? ["/panel", "nav.panel", "📊"] : role === "master" ? ["/master", "nav.master", "✂️"] : role === "admin" ? ["/admin", "nav.admin", "🛡️"] : null;

  return (
    <>
      <header className="header">
        <Link to="/" className="brand">
          <span className="brand-mark">✂</span>
          BarberShop
        </Link>

        <nav className="nav nav-desktop">
          <NavLink to="/" end>{t("nav.shops")}</NavLink>
          {user && <NavLink to="/bookings">{t("nav.bookings")}</NavLink>}
          {panel && <NavLink to={panel[0]}>{t(panel[1])}</NavLink>}
          {user && <NavLink to="/profile">{t("nav.profile")}</NavLink>}
          {user ? (
            <button className="link" onClick={logout}>{t("nav.logout")}</button>
          ) : (
            <NavLink to="/login">{t("nav.login")}</NavLink>
          )}
        </nav>

        <div className="row" style={{ margin: 0, gap: ".4rem", flexWrap: "nowrap" }}>
          <select className="lang" value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
            {LANG_LIST.map((l) => (
              <option key={l} value={l}>{l.toUpperCase()}</option>
            ))}
          </select>
          <button className="icon-btn" onClick={toggleTheme} aria-label="Theme" title="Theme">
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
        </div>
      </header>

      <main className="container">{children}</main>

      <nav className="bottom-nav" aria-label="Menu">
        <NavLink to="/" end><span className="ico">🏠</span>{t("nav.shops")}</NavLink>
        {user && <NavLink to="/bookings"><span className="ico">📅</span>{t("nav.bookings")}</NavLink>}
        {panel && <NavLink to={panel[0]}><span className="ico">{panel[2]}</span>{t(panel[1])}</NavLink>}
        {user && <NavLink to="/profile"><span className="ico">👤</span>{t("nav.profile")}</NavLink>}
        {user ? (
          <button onClick={logout}><span className="ico">🚪</span>{t("nav.logout")}</button>
        ) : (
          <NavLink to="/login"><span className="ico">👤</span>{t("nav.login")}</NavLink>
        )}
      </nav>
    </>
  );
}
