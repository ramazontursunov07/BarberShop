import { Link, NavLink } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Layout({ children }) {
  const { user, logout } = useAuth();
  return (
    <>
      <header className="header">
        <Link to="/" className="brand">
          ✂ BarberShop
        </Link>
        <nav className="nav">
          <NavLink to="/" end>
            Sartaroshxonalar
          </NavLink>
          {user && <NavLink to="/bookings">Bronlarim</NavLink>}
          {user ? (
            <button className="link" onClick={logout}>
              Chiqish
            </button>
          ) : (
            <NavLink to="/login">Kirish</NavLink>
          )}
        </nav>
      </header>
      <main className="container">{children}</main>
    </>
  );
}
