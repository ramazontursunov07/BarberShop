import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { useI18n } from "../i18n.jsx";
import { LANG_LIST } from "../locales.js";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const role = user?.role;

  return (
    <>
      <header className="header">
        <Link to="/" className="brand">
          ✂ BarberShop
        </Link>
        <nav className="nav">
          <NavLink to="/" end>
            {t("nav.shops")}
          </NavLink>
          {user && <NavLink to="/bookings">{t("nav.bookings")}</NavLink>}
          {role === "owner" && <NavLink to="/panel">{t("nav.panel")}</NavLink>}
          {role === "master" && <NavLink to="/master">{t("nav.master")}</NavLink>}
          {role === "admin" && <NavLink to="/admin">{t("nav.admin")}</NavLink>}
          {user ? (
            <button className="link" onClick={logout}>
              {t("nav.logout")}
            </button>
          ) : (
            <NavLink to="/login">{t("nav.login")}</NavLink>
          )}
          <select className="lang" value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language">
            {LANG_LIST.map((l) => (
              <option key={l} value={l}>
                {l.toUpperCase()}
              </option>
            ))}
          </select>
        </nav>
      </header>
      <main className="container">{children}</main>
    </>
  );
}
