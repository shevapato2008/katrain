import { Box } from '@mui/material';
import { Outlet } from 'react-router-dom';
import StatusBar from './StatusBar';
import NavigationRail from './NavigationRail';

interface KioskLayoutProps {
  username?: string;
}

const KioskLayout = ({ username }: KioskLayoutProps) => {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        bgcolor: 'background.default',
      }}
    >
      <StatusBar username={username} />
      <Box sx={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
        <NavigationRail />
        <Box
          component="main"
          sx={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column' }}
        >
          <Outlet />
        </Box>
      </Box>
    </Box>
  );
};

export default KioskLayout;
