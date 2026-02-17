import { Navigate, Outlet } from 'react-router-dom';
import { useKioskAuth } from '../../context/KioskAuthContext';

const KioskAuthGuard = () => {
  const { isAuthenticated } = useKioskAuth();
  if (!isAuthenticated) return <Navigate to="/kiosk/login" replace />;
  return <Outlet />;
};

export default KioskAuthGuard;
