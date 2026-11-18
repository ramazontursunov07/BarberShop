import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import { useI18n } from "./i18n.jsx";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import ForgotPassword from "./pages/ForgotPassword.jsx";
import Shops from "./pages/Shops.jsx";
import ShopPage from "./pages/ShopPage.jsx";
import Assistant from "./pages/Assistant.jsx";
import Hairstyle from "./pages/Hairstyle.jsx";
import Profile from "./pages/Profile.jsx";
import MyBookings from "./pages/MyBookings.jsx";
import OwnerPanel from "./pages/owner/OwnerPanel.jsx";
import MasterPanel from "./pages/master/MasterPanel.jsx";
import AdminPanel from "./pages/admin/AdminPanel.jsx";

function Protected({ roles, children }) {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  const location = useLocation();
  if (loading) return <p className="muted">{t("loading")}</p>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Shops />} />
        <Route path="/shop/:id" element={<ShopPage />} />
        <Route path="/login" element={<Login />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/assistant" element={<Assistant />} />
        <Route path="/hairstyle" element={<Hairstyle />} />
        <Route path="/profile" element={<Protected><Profile /></Protected>} />
        <Route
          path="/bookings"
          element={
            <Protected>
              <MyBookings />
            </Protected>
          }
        />
        <Route
          path="/panel"
          element={
            <Protected roles={["owner"]}>
              <OwnerPanel />
            </Protected>
          }
        />
        <Route
          path="/master"
          element={
            <Protected roles={["master"]}>
              <MasterPanel />
            </Protected>
          }
        />
        <Route
          path="/admin"
          element={
            <Protected roles={["admin"]}>
              <AdminPanel />
            </Protected>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Layout>
  );
}
