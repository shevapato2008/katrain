import { Box, Typography, Button } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';

export default function AccountSection() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const handleLogout = async () => {
    await logout();
    navigate('/kiosk/login', { replace: true });
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
          <Typography variant="body1" sx={{ color: 'text.primary', fontWeight: 600 }}>
            {user?.username ?? t('Guest', '访客')}
          </Typography>
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {t('Signed in', '已登录')} · {t('StellaBox account', '智星盒账户')}
          </Typography>
        </Box>
      </Box>
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
    </Box>
  );
}
