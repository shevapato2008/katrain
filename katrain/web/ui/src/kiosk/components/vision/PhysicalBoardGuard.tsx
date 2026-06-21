import { useState, type ReactNode } from 'react';
import { Alert, Box, Button, CircularProgress, LinearProgress, Typography } from '@mui/material';
import { useGeometry } from '../../context/GeometryContext';

const ACTIVE = new Set(['waiting_empty', 'dark_reference', 'flashing_corners', 'verifying', 'building_baseline']);

const PhysicalBoardGuard = ({ children, requireRecognition = false }: { children: ReactNode; requireRecognition?: boolean }) => {
  const { status, startCalibration } = useGeometry();
  const [starting, setStarting] = useState(false);
  const ready = status.phase === 'disabled' || (
    status.phase === 'ready' && status.session_calibrated && status.capabilities.geometry_ready
    && (!requireRecognition || status.capabilities.recognition_ready)
  );

  if (ready) return <>{children}</>;

  const start = async () => {
    setStarting(true);
    try { await startCalibration('auto'); } finally { setStarting(false); }
  };
  const progress = status.progress;
  const active = ACTIVE.has(status.phase);

  return (
    <Box sx={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
      <Box sx={{ width: '100%', maxWidth: 560, textAlign: 'center', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <Typography variant="h4">请清空棋盘</Typography>
        <Typography color="text.secondary">移除所有黑白棋子，系统将依次点亮四角和九个星位完成自动标定。</Typography>
        {active && <>
          <CircularProgress sx={{ alignSelf: 'center' }} />
          <LinearProgress variant={progress ? 'determinate' : 'indeterminate'} value={progress ? progress.current / progress.total * 100 : 0} />
          {progress && <Typography>{progress.current}/{progress.total}</Typography>}
        </>}
        {(status.phase === 'failed' || status.phase === 'degraded') && <Alert severity="error">{status.error ?? '标定失败，请清空棋盘后重试'}</Alert>}
        {requireRecognition && status.phase === 'ready' && !status.capabilities.recognition_ready && (
          <Alert severity="warning">棋盘已标定，但识别模型尚未就绪</Alert>
        )}
        {!active && <Button variant="contained" size="large" disabled={starting} onClick={start}>开始自动标定</Button>}
      </Box>
    </Box>
  );
};

export default PhysicalBoardGuard;
