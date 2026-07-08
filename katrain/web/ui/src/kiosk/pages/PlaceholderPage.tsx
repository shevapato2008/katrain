import { Box, Typography } from '@mui/material';
import { useLocation } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';

const PlaceholderPage = () => {
  const { t } = useTranslation();
  const location = useLocation();
  const segment = location.pathname.split('/').filter(Boolean).pop() || 'home';

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
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
  );
};

export default PlaceholderPage;
