import { Navigate, Outlet } from 'react-router-dom';
import { Box, CircularProgress } from '@mui/material';
import { useAuth } from '../../../context/AuthContext';

// LOGOUT_REDIRECT contract (consumed by Settings 退出登录, Phase B):
//   AuthContext.logout() only clears state — it does NOT navigate.
//   This guard bounces any unauthenticated view to /kiosk/login (Navigate below).
//   Callers must run: await logout(); navigate('/kiosk/login', { replace: true }).
const KioskAuthGuard = () => {
  const { isAuthenticated, isLoading } = useAuth();
  // Wait for the mount-time session probe (localStorage token OR shared SSO
  // cookie) before deciding — else a valid session flashes the login page.
  if (isLoading) {
    return (
      <Box
        sx={{
          height: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'background.default',
        }}
      >
        <CircularProgress sx={{ color: '#58b57a' }} />
      </Box>
    );
  }
  return isAuthenticated ? <Outlet /> : <Navigate to="/kiosk/login" replace />;
};

export default KioskAuthGuard;
