import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';

// LOGOUT_REDIRECT contract (consumed by Settings 退出登录, Phase B):
//   AuthContext.logout() only clears state — it does NOT navigate.
//   This guard bounces any unauthenticated view to /kiosk/login (Navigate below).
//   Callers must run: await logout(); navigate('/kiosk/login', { replace: true }).
const KioskAuthGuard = () => {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <Outlet /> : <Navigate to="/kiosk/login" replace />;
};

export default KioskAuthGuard;
