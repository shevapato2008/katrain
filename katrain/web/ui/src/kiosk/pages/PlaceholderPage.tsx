import { Box, Typography } from '@mui/material';
import { useLocation, useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { KioskPagebar } from '../shell/KioskPagebar';

const PlaceholderPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const segment = location.pathname.split('/').filter(Boolean).pop() || 'home';

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <KioskPagebar title={t('Coming soon', '敬请期待')} backLabel={t('Back', '返回')} onBack={() => navigate(-1)} />
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flex: 1,
          minHeight: 0,
          flexDirection: 'column',
          gap: 2,
        }}
      >
        <Typography variant="h3" sx={{ color: 'text.secondary', opacity: 0.3 }}>
          {segment.toUpperCase()}
        </Typography>
        <Typography variant="body2" sx={{ color: 'text.secondary' }}>
          {t('Coming soon', '敬请期待')}
        </Typography>
      </Box>
    </Box>
  );
};

export default PlaceholderPage;
