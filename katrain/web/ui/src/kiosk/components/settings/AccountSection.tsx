import { Box, Typography, Button } from '@mui/material';
import LogoutIcon from '@mui/icons-material/Logout';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { useAiLadderStatus } from '../../../features/aiLadder/useAiLadderStatus';
import AiLadderStatusCard from '../../../features/aiLadder/AiLadderStatusCard';

export default function AccountSection() {
  const { user, logout, token } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { status, retry } = useAiLadderStatus(token ?? undefined, Boolean(user));

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
      {user && <Box sx={{ mb: 1 }}><AiLadderStatusCard status={status} onRetry={retry} compact /></Box>}
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
