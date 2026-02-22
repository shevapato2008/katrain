import { Box, Typography } from '@mui/material';

interface StatusBarProps {
  username?: string;
}

const StatusBar = ({ username }: StatusBarProps) => {
  return (
    <Box
      sx={{
        height: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 2,
        borderBottom: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
        flexShrink: 0,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Typography variant="body2" sx={{ fontWeight: 700, color: 'primary.main' }}>
          弈航
        </Typography>
        <Box
          data-testid="engine-status"
          sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'success.main' }}
        />
      </Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
        {username && (
          <Typography variant="body2" sx={{ color: 'text.secondary' }}>
            {username}
          </Typography>
        )}
        <Typography
          data-testid="clock"
          variant="caption"
          sx={{ color: 'text.secondary' }}
        >
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </Typography>
      </Box>
    </Box>
  );
};

export default StatusBar;
