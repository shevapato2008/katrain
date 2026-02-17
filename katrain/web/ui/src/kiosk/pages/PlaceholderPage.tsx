import { Box, Typography } from '@mui/material';
import { useLocation } from 'react-router-dom';

const PlaceholderPage = () => {
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
        Coming soon
      </Typography>
    </Box>
  );
};

export default PlaceholderPage;
