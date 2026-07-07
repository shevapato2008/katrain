import { useState, useEffect } from 'react';
import { Box, Typography, IconButton, Tooltip } from '@mui/material';
import { Videocam, GridOn } from '@mui/icons-material';
import { useOptionalVision } from '../../context/VisionContext';
import { useOptionalGeometry } from '../../context/GeometryContext';

interface HeaderProps {
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
  const vision = useOptionalVision();
  if (!vision) return null;
  const { visionStatus } = vision;

  if (!visionStatus.enabled) return null;

  const cameraColor = visionStatus.cameraConnected ? 'success.main' : 'error.main';
  const cameraLabel = visionStatus.cameraConnected ? '摄像头已连接' : '摄像头未连接';

  return (
    <>
      {/* Camera status — click to open vision setup */}
      <Tooltip title={cameraLabel} arrow>
        <IconButton
          component="a"
          href="/kiosk/vision/setup"
          size="small"
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

/** Geometry/calibration status icon — only rendered when the GeometryProvider is available */
const GeometryIndicator = () => {
  const geometry = useOptionalGeometry();
  if (!geometry) return null;
  const { status } = geometry;
  if (status.phase === 'disabled') return null;
  const color =
    status.phase === 'ready'
      ? 'success.main'
      : status.phase === 'degraded' || status.phase === 'failed'
        ? 'error.main'
        : 'warning.main';
  return (
    <Tooltip title={status.phase === 'ready' ? '棋盘标定正常' : '需要标定棋盘'} arrow>
      <IconButton component="a" href="/kiosk/vision/setup" size="small" aria-label="棋盘标定状态" sx={{ p: 0.25 }}>
        <GridOn sx={{ fontSize: 18, color }} />
      </IconButton>
    </Tooltip>
  );
};

const Header = ({ username }: HeaderProps) => {
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
        height: 50,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        px: 3,
        borderBottom: '1px solid',
        borderColor: 'divider',
        bgcolor: 'background.default',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: '11px' }}>
          <img
            src="/assets/img/logo-white.png"
            alt="智星盒 StellaBox"
            style={{ width: 34, height: 34, objectFit: 'contain' }}
          />
          <Box sx={{ display: 'flex', alignItems: 'baseline' }}>
            <Typography sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 600, fontSize: 20 }}>
              智星盒
            </Typography>
            <Typography
              component="span"
              sx={{
                fontFamily: "'Newsreader','Noto Serif SC',serif",
                fontStyle: 'italic',
                fontSize: 12,
                color: 'text.secondary',
                ml: '7px',
              }}
            >
              StellaBox
            </Typography>
          </Box>
        </Box>
        <Box
          data-testid="engine-status"
          aria-label="engine assumed-ready"
          sx={{ width: 6, height: 6, borderRadius: '50%', bgcolor: 'success.main' }}
        />
        <VisionIndicators />
        <GeometryIndicator />
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
          sx={{ color: 'text.secondary', fontVariantNumeric: 'tabular-nums' }}
        >
          {time}
        </Typography>
      </Box>
    </Box>
  );
};

export default Header;
