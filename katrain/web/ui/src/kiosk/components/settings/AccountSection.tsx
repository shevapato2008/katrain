import { Box, Typography, Button, Chip } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';

// Decision B (logout-then-register): the kiosk never talks to the cross-origin
// auth endpoints itself. A guest who wants to register/sign in is sent to the
// setup-wizard's launcher gate via a top-level browser navigation, which logs
// the shared guest session out and opens the real auth flow there.
const SETUP_WIZARD_ORIGIN = import.meta.env.VITE_SETUP_WIZARD_ORIGIN || 'http://127.0.0.1:8080';

export default function AccountSection() {
  const { user, logout, isGuest } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleLogout = async () => {
    await logout();
    navigate('/kiosk/login', { replace: true });
  };

  const handleRegisterLogin = () => {
    window.location.href = `${SETUP_WIZARD_ORIGIN}/launcher?logout=1&authmode=register`;
  };

  return (
    <Box>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          bgcolor: 'background.paper',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 2,
          px: 2,
          py: 1.5,
          mb: 1.5,
        }}
      >
        <Box>
          {isGuest ? (
            <Chip label={t('Guest', '访客')} size="small" data-testid="account-guest-chip" />
          ) : (
            <Typography variant="body1" sx={{ color: 'text.primary', fontWeight: 600 }}>
              {user?.username ?? t('Guest', '访客')}
            </Typography>
          )}
          <Typography variant="body2" sx={{ color: 'text.secondary', mt: isGuest ? 0.75 : 0 }}>
            {isGuest
              ? t('Not signed in', '未登录')
              : `${t('Signed in', '已登录')} · ${t('StellaBox account', '智星盒账户')}`}
          </Typography>
        </Box>
      </Box>
      {isGuest ? (
        <Button
          variant="contained"
          onClick={handleRegisterLogin}
          data-testid="account-register-login"
          fullWidth
        >
          {t('Register / Sign in', '注册 / 登录')}
        </Button>
      ) : (
        <Button
          variant="outlined"
          color="error"
          startIcon={<LogoutIcon />}
          onClick={handleLogout}
          data-testid="settings-logout"
          fullWidth
        >
          {t('Sign out', '退出登录')}
        </Button>
      )}
    </Box>
  );
}
