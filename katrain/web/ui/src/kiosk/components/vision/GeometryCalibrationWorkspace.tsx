import { useCallback, useEffect, useState } from 'react';
import { Alert, Box, Button, Chip, CircularProgress, LinearProgress, Typography } from '@mui/material';
import { Cancel, Refresh } from '@mui/icons-material';
import { GeometryAPI, type GeometryLayout } from '../../../api/geometryApi';
import { useGeometry } from '../../context/GeometryContext';
import CameraGeometryOverlay from './CameraGeometryOverlay';
import GeometryVideoPanel from './GeometryVideoPanel';
import {
  buildAnchorGeometryModel,
  buildRawGeometryModel,
  buildWarpedGeometryModel,
  type OverlayViewport,
} from './geometryOverlay';

const ACTIVE = new Set(['waiting_empty', 'dark_reference', 'flashing_corners', 'verifying', 'building_baseline']);

const PHASE_LABELS: Record<string, string> = {
  waiting_empty: '准备空盘标定',
  dark_reference: '采集熄灯参考帧',
  flashing_corners: '定位棋盘四角',
  verifying: '定位九个星位',
  building_baseline: '生成空盘基线',
  cancelled: '标定已取消',
};

interface GeometryCalibrationWorkspaceProps {
  mode: 'guard' | 'settings';
  requireRecognition?: boolean;
}

const GeometryCalibrationWorkspace = ({ mode, requireRecognition = false }: GeometryCalibrationWorkspaceProps) => {
  const { status, startCalibration, cancelCalibration } = useGeometry();
  const [layout, setLayout] = useState<GeometryLayout | null>(null);
  const [rawFrame, setRawFrame] = useState<{ width: number; height: number } | null>(null);
  const [starting, setStarting] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [layoutError, setLayoutError] = useState<string | null>(null);
  const active = ACTIVE.has(status.phase);

  useEffect(() => {
    if (!status.last_valid && status.phase !== 'ready' && status.phase !== 'degraded') return;
    let cancelled = false;
    GeometryAPI.layout()
      .then((value) => {
        if (!cancelled) {
          setLayout(value);
          setLayoutError(null);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : '无法读取棋盘几何';
        if (!message.includes('409')) setLayoutError(message);
      });
    return () => { cancelled = true; };
  }, [status.geometry_revision, status.last_valid, status.phase]);

  const rawModelForViewport = useCallback((viewport: OverlayViewport) => {
    if (active) {
      const frame = rawFrame ?? layout?.frame;
      if (!frame) return null;
      return buildAnchorGeometryModel(status.detected_anchors ?? [], frame, viewport);
    }
    return layout ? buildRawGeometryModel(layout, status.phase, viewport) : null;
  }, [active, layout, rawFrame, status.detected_anchors, status.phase]);
  const warpedModelForViewport = useCallback((viewport: OverlayViewport) => {
    if (!layout) return null;
    return buildWarpedGeometryModel(layout.out_size, layout.stale ? 'degraded' : status.phase, viewport);
  }, [layout, status.phase]);

  const start = async () => {
    setStarting(true);
    setActionError(null);
    try {
      await startCalibration(status.phase === 'required' ? 'auto' : 'manual');
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '无法启动标定');
    } finally {
      setStarting(false);
    }
  };

  const cameraReady = status.capabilities.camera_ready;
  const ledReady = status.capabilities.led_ready;
  const canStart = cameraReady && ledReady && !starting && !active;
  const progress = status.progress;
  const metrics = status.metrics ?? {};
  const buttonLabel = status.phase === 'ready'
    ? '重新标定'
    : status.phase === 'degraded'
      ? '已清空，重新标定'
      : '已清空，开始自动标定';

  return (
    <Box sx={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1.5, p: mode === 'guard' ? 2 : 0 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            {status.phase === 'degraded'
              ? '摄像头或棋盘位置已变化'
              : status.phase === 'ready'
                ? '棋盘定位完成'
                : active
                  ? PHASE_LABELS[status.phase]
                  : '请清空棋盘'}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {status.phase === 'degraded'
              ? '红色网格是上一次定位结果。请清空棋盘并确认后重新标定。'
              : '系统通过四角和九个星位 LED 定位，完成后显示四角、网格线和 361 个落子点。'}
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip size="small" color={cameraReady ? 'success' : 'error'} label={cameraReady ? '摄像头已连接' : '摄像头未连接'} />
          <Chip size="small" color={ledReady ? 'success' : 'error'} label={ledReady ? 'LED 已连接' : 'LED 未连接'} />
        </Box>
      </Box>

      {(status.phase === 'degraded' || status.phase === 'failed') && (
        <Alert severity="error">{status.phase === 'degraded' ? '当前定位已失效，实体棋盘功能已暂停。' : status.error ?? '标定失败'}</Alert>
      )}
      {requireRecognition && status.phase === 'ready' && !status.capabilities.recognition_ready && (
        <Alert severity="warning">棋盘已标定，但识别模型尚未就绪</Alert>
      )}
      {actionError && <Alert severity="error">{actionError}</Alert>}
      {layoutError && <Alert severity="warning">几何叠加读取失败：{layoutError}</Alert>}

      <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: { xs: 'column', lg: 'row' }, gap: 2, overflow: 'auto' }}>
        <GeometryVideoPanel
          title="摄像头原始画面"
          src="/api/v1/geometry/stream"
          alt="摄像头原始画面"
          aspectRatio="16 / 9"
          onImageLoad={setRawFrame}
          overlay={<CameraGeometryOverlay modelForViewport={rawModelForViewport} label="原始画面棋盘几何叠加层" />}
        />
        <GeometryVideoPanel
          title="俯视矫正画面"
          src={layout ? `/api/v1/geometry/warped-stream?revision=${layout.revision}` : undefined}
          alt="俯视矫正画面"
          aspectRatio="1 / 1"
          waitingText="完成 LED 标定后生成俯视画面"
          overlay={<CameraGeometryOverlay modelForViewport={warpedModelForViewport} label="俯视画面棋盘几何叠加层" />}
        />
      </Box>

      {active && (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
            <CircularProgress size={20} />
            <Typography>{progress ? `${progress.current}/${progress.total}` : '准备中'}</Typography>
          </Box>
          <LinearProgress variant={progress ? 'determinate' : 'indeterminate'} value={progress ? progress.current / progress.total * 100 : 0} />
        </Box>
      )}

      {status.phase === 'ready' && (
        <Typography variant="body2" color="success.main" sx={{ textAlign: 'center' }}>
          {`${metrics.inlier_count ?? 13}/13 · RMS ${Number(metrics.rms_residual ?? 0).toFixed(3)} px · 最大残差 ${Number(metrics.max_residual ?? 0).toFixed(3)} px`}
        </Typography>
      )}

      <Box sx={{ display: 'flex', justifyContent: 'center', gap: 1.5 }}>
        {active ? (
          <Button variant="outlined" color="warning" startIcon={<Cancel />} onClick={() => void cancelCalibration()}>
            取消标定
          </Button>
        ) : (
          <Button
            variant="contained"
            size="large"
            startIcon={<Refresh />}
            disabled={!canStart}
            onClick={() => void start()}
            sx={{ minWidth: 240, minHeight: 48 }}
          >
            {buttonLabel}
          </Button>
        )}
      </Box>
    </Box>
  );
};

export default GeometryCalibrationWorkspace;
