import { useCallback, useEffect, useState } from 'react';
import { Alert, alpha, Box, Button, Chip, CircularProgress, LinearProgress, ToggleButton, ToggleButtonGroup, Typography } from '@mui/material';
import { Cancel, CheckCircle, ErrorOutline, Refresh, WarningAmberOutlined } from '@mui/icons-material';
import { GeometryAPI, type GeometryLayout } from '../../../api/geometryApi';
import { useGeometry } from '../../context/GeometryContext';
import CameraGeometryOverlay from './CameraGeometryOverlay';
import GeometryVideoPanel from './GeometryVideoPanel';
import { KIOSK_SERIF } from '../../theme';
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

const GTP_LETTERS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';

function gtpPoint(row: number, col: number): string {
  return `${GTP_LETTERS[col] ?? '?'}${19 - row}`;
}

function buildDiagnostic(error?: string | null) {
  const raw = error ?? '';
  const anchor = raw.match(/^anchor_not_found:(\d+),(\d+)$/);
  if (anchor) {
    const row = Number(anchor[1]);
    const col = Number(anchor[2]);
    return {
      title: `无法定位 ${gtpPoint(row, col)} 的定位灯`,
      body: '通常是棋子遮挡星位、LED 没亮或太暗、摄像头画面偏移，导致系统看不到这一个定位点。',
      action: '如果右侧俯视网格仍然对齐实体棋盘，可以直接使用上次标定；否则请清空棋盘后重新标定。',
      detail: raw,
    };
  }
  if (raw === 'board_moved') {
    return {
      title: '摄像头或棋盘位置发生变化',
      body: '系统检测到实时画面和上次标定结果不再对齐，实体棋盘功能已暂停。',
      action: '请固定摄像头和棋盘，清空棋盘后重新标定。',
      detail: raw,
    };
  }
  if (raw === 'non_empty_baseline' || raw.includes('empty baseline')) {
    return {
      title: '棋盘没有清空，无法建立空盘基线',
      body: '自动标定需要先记录没有棋子的棋盘画面。当前画面里仍可能有棋子或明显遮挡。',
      action: '请清空棋盘，确认所有定位灯可见后再重试。',
      detail: raw,
    };
  }
  return {
    title: '自动标定失败',
    body: '系统没有完成这次棋盘定位。通常需要检查摄像头、LED 连接和棋盘是否清空。',
    action: '如果网格仍然对齐，可以使用上次标定；否则请清空棋盘后重试。',
    detail: raw || 'calibration_failed',
  };
}

interface GeometryCalibrationWorkspaceProps {
  mode: 'guard' | 'settings';
  requireRecognition?: boolean;
}

const GeometryCalibrationWorkspace = ({ mode, requireRecognition = false }: GeometryCalibrationWorkspaceProps) => {
  const { status, startCalibration, confirmExisting, cancelCalibration } = useGeometry();
  const [layout, setLayout] = useState<GeometryLayout | null>(null);
  const [rawFrame, setRawFrame] = useState<{ width: number; height: number } | null>(null);
  const [starting, setStarting] = useState(false);
  const [confirmingManual, setConfirmingManual] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [layoutError, setLayoutError] = useState<string | null>(null);
  // Single large preview: show 摄像头原始 (with anchor/grid overlay) by default and while
  // calibrating (so you see the LEDs being located); auto-switch to 俯视矫正 once locked so you
  // can verify the rectified grid. A manual toggle overrides the auto choice.
  const [manualView, setManualView] = useState<'raw' | 'warped' | null>(null);
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
    return buildWarpedGeometryModel(
      layout.out_size,
      layout.stale ? 'degraded' : status.phase,
      viewport,
      layout.warped_margin_cells ?? 0,
    );
  }, [layout, status.phase]);

  const start = async () => {
    setStarting(true);
    setActionError(null);
    try {
      await startCalibration(status.phase === 'required' ? 'auto' : 'manual');
      setConfirmingManual(false);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '无法启动标定');
    } finally {
      setStarting(false);
    }
  };

  const handleStart = () => {
    if (status.phase === 'ready' && !confirmingManual) {
      setConfirmingManual(true);
      return;
    }
    void start();
  };

  const reuseExisting = async () => {
    setStarting(true);
    setActionError(null);
    try {
      await confirmExisting();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '无法使用上次标定');
    } finally {
      setStarting(false);
    }
  };

  const cameraReady = status.capabilities.camera_ready;
  const ledReady = status.capabilities.led_ready;
  const canStart = cameraReady && ledReady && !starting && !active;
  const canReuse = (status.phase === 'required' || status.phase === 'failed') && status.last_valid && cameraReady && !starting && !active;
  const progress = status.progress;
  const metrics = status.metrics ?? {};
  const diagnostic = status.phase === 'failed' ? buildDiagnostic(status.error) : null;
  const buttonLabel = status.phase === 'ready' && !confirmingManual
    ? '重新标定'
    : status.phase === 'degraded'
      ? '已清空，重新标定'
      : '已清空，开始自动标定';

  // Single large preview: default 摄像头原始 (shows the LED anchors while calibrating), auto-swap
  // to 俯视矫正 once locked so the operator verifies the rectified grid; manual toggle overrides.
  const view: 'raw' | 'warped' = manualView ?? (!active && status.phase === 'ready' && layout ? 'warped' : 'raw');

  const phaseTitle =
    status.phase === 'degraded' ? '摄像头或棋盘位置已变化'
      : status.phase === 'ready' ? '棋盘定位完成'
        : status.phase === 'failed' ? '自动标定失败'
          : status.phase === 'required' && status.last_valid ? '请确认棋盘定位'
            : active ? PHASE_LABELS[status.phase]
              : '请清空棋盘';

  const phaseHint =
    status.phase === 'degraded' ? '红色网格是上一次定位结果。请清空棋盘并确认后重新标定。'
      : status.phase === 'failed' ? '请根据诊断信息选择继续使用上次标定，或清空棋盘后重试。'
        : status.phase === 'required' && status.last_valid ? '请检查实时画面中的四角、网格线和 361 个落子点是否仍与实体棋盘对齐。'
          : '系统通过四角和九个星位 LED 定位，完成后显示四角、网格线和 361 个落子点。';

  const preview = view === 'raw' ? (
    <GeometryVideoPanel
      fill
      src="/api/v1/geometry/stream"
      alt="摄像头原始画面"
      onImageLoad={setRawFrame}
      overlay={<CameraGeometryOverlay modelForViewport={rawModelForViewport} label="原始画面棋盘几何叠加层" />}
    />
  ) : (
    <GeometryVideoPanel
      fill
      src={layout ? `/api/v1/geometry/warped-stream?revision=${layout.revision}` : undefined}
      alt="俯视矫正画面"
      waitingText="完成 LED 标定后生成俯视画面"
      overlay={<CameraGeometryOverlay modelForViewport={warpedModelForViewport} label="俯视画面棋盘几何叠加层" />}
    />
  );

  return (
    <Box sx={{ width: '100%', height: '100%', minHeight: 0, display: 'flex', flexDirection: { xs: 'column', md: 'row' }, gap: 2, p: mode === 'guard' ? 2 : 0 }}>
      {/* LEFT — segmented view toggle + one large preview so the 19×19 grid stays legible on 7". */}
      <Box sx={{ flex: 1, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1 }}>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={view}
          onChange={(_, next) => { if (next) setManualView(next); }}
          sx={{ alignSelf: 'flex-start' }}
        >
          <ToggleButton value="warped" sx={{ px: 2 }}>俯视矫正画面</ToggleButton>
          <ToggleButton value="raw" sx={{ px: 2 }}>摄像头原始画面</ToggleButton>
        </ToggleButtonGroup>
        {preview}
      </Box>

      {/* RIGHT — status, diagnostics, and actions rail. */}
      <Box sx={{ flex: { xs: 'none', md: '0 0 300px' }, minWidth: 0, minHeight: 0, display: 'flex', flexDirection: 'column', gap: 1.25, overflow: 'auto' }}>
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Chip size="small" color={cameraReady ? 'success' : 'error'} label={cameraReady ? '摄像头已连接' : '摄像头未连接'} />
          <Chip size="small" color={ledReady ? 'success' : 'error'} label={ledReady ? 'LED 已连接' : 'LED 未连接'} />
        </Box>

        <Box>
          <Typography variant="h6" sx={{ fontFamily: KIOSK_SERIF, fontWeight: 500 }}>{phaseTitle}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>{phaseHint}</Typography>
        </Box>

        {!active && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }} data-testid="geometry-led-advisory">
            <WarningAmberOutlined sx={{ fontSize: 18, color: 'warning.main' }} />
            <Typography variant="body2" sx={{ color: 'warning.main' }}>
              先清空棋盘 · 手动触发 · 不会自动点亮 LED
            </Typography>
          </Box>
        )}

        {status.phase === 'degraded' && (
          <Alert severity="error">当前定位已失效，实体棋盘功能已暂停。</Alert>
        )}
        {diagnostic && (
          <Box
            data-testid="geometry-diagnostic-card"
            sx={{
              display: 'grid',
              gridTemplateColumns: 'auto 1fr',
              gap: 1.5,
              p: 2,
              borderRadius: 2,
              bgcolor: (t) => alpha(t.palette.warning.main, 0.1),
              border: (t) => `1px solid ${alpha(t.palette.warning.main, 0.45)}`,
            }}
          >
            <ErrorOutline sx={{ color: 'warning.main', mt: 0.25 }} />
            <Box>
              <Typography sx={{ fontWeight: 800 }}>{diagnostic.title}</Typography>
              <Typography variant="body2" sx={{ color: 'text.secondary', mt: 0.5 }}>{diagnostic.body}</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 1 }}>
                <CheckCircle sx={{ fontSize: 18, color: 'success.main' }} />
                <Typography variant="body2">{diagnostic.action}</Typography>
              </Box>
              <Typography variant="caption" sx={{ display: 'block', color: 'text.disabled', mt: 1 }}>
                技术细节：{diagnostic.detail}
              </Typography>
            </Box>
          </Box>
        )}
        {requireRecognition && status.phase === 'ready' && !status.capabilities.recognition_ready && (
          <Alert severity="warning">棋盘已标定，但识别模型尚未就绪</Alert>
        )}
        {confirmingManual && (
          <Alert severity="warning">请先清空实体棋盘，再启动 LED 自动标定。</Alert>
        )}
        {actionError && <Alert severity="error">{actionError}</Alert>}
        {layoutError && <Alert severity="warning">几何叠加读取失败：{layoutError}</Alert>}
        {canReuse && <Alert severity="info">网格对齐时可直接继续，<strong>无需清空棋盘</strong>。</Alert>}

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

        <Box sx={{ flexGrow: 1 }} />

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
          {active ? (
            <Button variant="outlined" color="warning" startIcon={<Cancel />} onClick={() => void cancelCalibration()} sx={{ minHeight: 48 }}>
              取消标定
            </Button>
          ) : (
            <>
              {canReuse && (
                <Button
                  variant="outlined"
                  color="success"
                  size="large"
                  disabled={starting}
                  onClick={() => void reuseExisting()}
                  sx={{ minHeight: 48 }}
                >
                  网格无误，使用上次标定
                </Button>
              )}
              <Button
                variant="contained"
                size="large"
                startIcon={<Refresh />}
                disabled={!canStart}
                onClick={handleStart}
                sx={{ minHeight: 48 }}
              >
                {buttonLabel}
              </Button>
            </>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default GeometryCalibrationWorkspace;
