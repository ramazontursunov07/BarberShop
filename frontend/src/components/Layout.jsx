import { useState } from "react";
import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { LANG_LIST } from "../locales.js";
import { applyTheme, getTheme } from "../theme.js";
import Icon from "./Icon.jsx";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [theme, setTheme] = useState(getTheme);
  const role = user?.role;

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  };

  const staff = role === "owner" ? ["/panel", t("nav.panel")] : role === "master" ? ["/master", t("nav.master")] : role === "admin" ? ["/admin", t("nav.admin")] : null;

  return (
    <>
      <header className="header">
        <div className="header-in">
          <Link to="/" className="brand">
            <span className="logo"><Icon name="scissors" size={19} /></span>
            <span>BarberShop</span>
          </Link>
          <nav className="nav">
            <NavLink to="/" end className="desktop-only"><Icon name="home" size={18} />{t("nav.shops")}</NavLink>
            <NavLink to="/assistant" className="desktop-only"><Icon name="sparkle" size={18} />{t("nav.ai")}</NavLink>
            <NavLink to="/hairstyle" className="desktop-only"><Icon name="camera" size={18} />{t("nav.style")}</NavLink>
            {user && <NavLink to="/bookings" className="desktop-only"><Icon name="calendar" size={18} />{t("nav.bookings")}</NavLink>}
            {user && <NavLink to="/profile" className="desktop-only"><Icon name="user" size={18} />{t("nav.profile")}</NavLink>}
            {staff && <NavLink to={staff[0]}><Icon name="settings" size={18} /><span className="nav-link-text">{staff[1]}</span></NavLink>}
            <select className="lang" value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
              {LANG_LIST.map((l) => <option key={l} value={l}>{l.toUpperCase()}</option>)}
            </select>
            <button className="icon-btn" onClick={toggleTheme} aria-label="Theme" title="Theme">
              <Icon name={theme === "dark" ? "sun" : "moon"} size={18} />
            </button>
            {user ? (
              <button className="icon-btn" onClick={logout} aria-label={t("nav.logout")} title={t("nav.logout")}><Icon name="logout" size={18} /></button>
            ) : (
              <NavLink to="/login"><Icon name="user" size={18} /><span className="nav-link-text">{t("nav.login")}</span></NavLink>
            )}
          </nav>
        </div>
      </header>

      <main className="container">{children}</main>

      <nav className="bottom-nav" aria-label="Menu">
        <NavLink to="/" end><Icon name="home" size={22} />{t("nav.home")}</NavLink>
        <NavLink to="/assistant"><Icon name="sparkle" size={22} />{t("nav.ai")}</NavLink>
        <NavLink to="/hairstyle"><Icon name="camera" size={22} />{t("nav.style")}</NavLink>
        <NavLink to="/bookings"><Icon name="calendar" size={22} />{t("nav.bookings")}</NavLink>
        {staff ? (
          <NavLink to={staff[0]}><Icon name="settings" size={22} />{staff[1]}</NavLink>
        ) : (
          <NavLink to={user ? "/profile" : "/login"}><Icon name="user" size={22} />{user ? t("nav.profile") : t("nav.login")}</NavLink>
        )}
      </nav>
    </>
  );
}
