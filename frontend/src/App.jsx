import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Shops from "./pages/Shops.jsx";
import ShopPage from "./pages/ShopPage.jsx";
import MyBookings from "./pages/MyBookings.jsx";

function Protected({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <p className="muted">Yuklanmoqda...</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  return children;
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Shops />} />
        <Route path="/shop/:id" element={<ShopPage />} />
        <Route path="/login" element={<Login />} />
        <Route
          path="/bookings"
          element={
            <Protected>
              <MyBookings />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
