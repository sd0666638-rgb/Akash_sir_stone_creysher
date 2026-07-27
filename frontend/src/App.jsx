import { Navigate, Route, Routes } from "react-router-dom";

import AppLayout from "./layouts/AppLayout.jsx";
import { useAuth } from "./context/AuthContext.jsx";
import CustomersPage from "./pages/CustomersPage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import InvoicesPage from "./pages/InvoicesPage.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import MaterialsPage from "./pages/MaterialsPage.jsx";
import PaymentsPage from "./pages/PaymentsPage.jsx";
import ReportsPage from "./pages/ReportsPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";

function Protected({ children }) {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Protected>
            <AppLayout />
          </Protected>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="customers" element={<CustomersPage />} />
        <Route path="materials" element={<MaterialsPage />} />
        <Route path="invoices" element={<InvoicesPage />} />
        <Route path="payments" element={<PaymentsPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}
