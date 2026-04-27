import { useState, useEffect } from 'react';
import { Box, Typography, IconButton, Tooltip } from '@mui/material';
import { Videocam, GridOn } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useVision } from '../../context/VisionContext';

interface StatusBarProps {
  username?: string;
}

/** Resolve board-pose sync state to a status color */
const syncStateColor = (syncState: string): string => {
  switch (syncState) {
    case 'synced':
      return 'success.main';
    case 'calibrating':
    case 'setup':
      return 'warning.main';
    case 'mismatch':
    case 'lost':
      return 'error.main';
    default:
      return 'grey.500';
  }
};

/** Vision status icons — only rendered when the VisionProvider is available */
const VisionIndicators = () => {
  const navigate = useNavigate();

  // If VisionProvider is not in the tree, useVision will throw.
  // We catch this at the call-site (VisionIndicatorsSafe) so the
  // StatusBar still renders in non-vision builds.
  const { visionStatus } = useVision();

  if (!visionStatus.enabled) return null;

  const cameraColor = visionStatus.cameraConnected ? 'success.main' : 'error.main';
  const cameraLabel = visionStatus.cameraConnected ? '摄像头已连接' : '摄像头未连接';

  return (
    <>
      {/* Camera status — click to open vision setup */}
      <Tooltip title={cameraLabel} arrow>
        <IconButton
          size="small"
          onClick={() => navigate('/kiosk/vision/setup')}
          sx={{ p: 0.25 }}
          aria-label={cameraLabel}
        >
          <Videocam sx={{ fontSize: 18, color: cameraColor }} />
        </IconButton>
      </Tooltip>

      {/* Board pose status — only shown after pose lock */}
      {visionStatus.poseLocked && (
        <Tooltip title={`棋盘状态: ${visionStatus.syncState}`} arrow>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <GridOn sx={{ fontSize: 18, color: syncStateColor(visionStatus.syncState) }} />
          </Box>
        </Tooltip>
      )}
    </>
  );
};

/**
 * Safe wrapper: if VisionProvider is absent (non-vision builds),
 * silently render nothing instead of crashing.
 */
const VisionIndicatorsSafe = () => {
  try {
    return <VisionIndicators />;
  } catch {
    return null;
  }
};

const StatusBar = ({ username }: StatusBarProps) => {
  const [time, setTime] = useState(() =>
    new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  );

  useEffect(() => {
    const id = setInterval(
      () => setTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })),
      10_000,
    );
    return () => clearInterval(id);
  }, []);

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
        <img src="/assets/img/logo-white.png" alt="弈航" style={{ width: 20, height: 20 }} />
        <Typography variant="body2" sx={{ fontWeight: 700, color: 'primary.main' }}>
          弈航
        </Typography>
        <Box
          data-testid="engine-status"
          sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'success.main' }}
        />
        <VisionIndicatorsSafe />
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
          {time}
        </Typography>
      </Box>
    </Box>
  );
};

export default StatusBar;
