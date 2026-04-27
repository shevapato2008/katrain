import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
  Snackbar,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
} from '@mui/material';
import { Warning as WarningIcon, CheckCircle as CheckIcon } from '@mui/icons-material';
import CaptureGuide from './CaptureGuide';
import type { VisionSyncEvent, SyncEventType } from '../../hooks/useVisionSync';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface VisionSyncOverlayProps {
  syncEvents: VisionSyncEvent[];
  onDismiss?: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SNACKBAR_DURATION = 5000;
const BOARD_LOST_THRESHOLD_MS = 10_000;

type ToastSeverity = 'warning' | 'success' | 'info' | 'error';

interface ToastConfig {
  message: string;
  severity: ToastSeverity;
  icon?: React.ReactNode;
}

const TOAST_MAP: Partial<Record<SyncEventType, ToastConfig>> = {
  degraded: {
    message: '检测质量下降，请检查光线',
    severity: 'warning',
    icon: <WarningIcon />,
  },
  board_reacquired: {
    message: '棋盘已重新检测到',
    severity: 'success',
    icon: <CheckIcon />,
  },
  ambiguous_stone: {
    message: '无法确定落子位置，请调整棋子',
    severity: 'warning',
    icon: <WarningIcon />,
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const VisionSyncOverlay = ({ syncEvents, onDismiss }: VisionSyncOverlayProps) => {
  // -- Toast state ----------------------------------------------------------
  const [toastOpen, setToastOpen] = useState(false);
  const [toastConfig, setToastConfig] = useState<ToastConfig | null>(null);

  // -- Modal: capture_pending -----------------------------------------------
  const [capturePositions, setCapturePositions] = useState<
    Array<{ row: number; col: number; color: number }> | null
  >(null);

  // -- Modal: illegal_change ------------------------------------------------
  const [illegalChangeOpen, setIllegalChangeOpen] = useState(false);

  // -- Modal: board_lost (>10s persistent) ----------------------------------
  const [boardLostOpen, setBoardLostOpen] = useState(false);
  const boardLostTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const boardLostActiveRef = useRef(false);

  // Track the latest event index so we only process new events.
  const processedRef = useRef(0);

  // Derive the latest unprocessed events.
  const newEvents = useMemo(
    () => syncEvents.slice(processedRef.current),
    [syncEvents],
  );

  // -- Close helpers --------------------------------------------------------
  const closeToast = useCallback(() => setToastOpen(false), []);

  const handleIllegalRestore = useCallback(() => {
    setIllegalChangeOpen(false);
    onDismiss?.();
  }, [onDismiss]);

  const handleIllegalIgnore = useCallback(() => {
    setIllegalChangeOpen(false);
  }, []);

  const handleCaptureDismiss = useCallback(() => {
    setCapturePositions(null);
  }, []);

  // -- Process new events ---------------------------------------------------
  useEffect(() => {
    if (newEvents.length === 0) return;

    for (const event of newEvents) {
      const eventType = event.type;

      // --- Toast events (non-blocking) ---
      if (eventType in TOAST_MAP) {
        const config = TOAST_MAP[eventType]!;
        setToastConfig(config);
        setToastOpen(true);
      }

      // --- Silent events ---
      if (eventType === 'move_confirmed') {
        // No UI needed.
      }

      // --- Capture pending (blocking modal) ---
      if (eventType === 'capture_pending') {
        const positions = event.data.positions as Array<{
          row: number;
          col: number;
          color: number;
        }> | undefined;
        if (positions && positions.length > 0) {
          setCapturePositions(positions);
        }
      }

      // --- Captures cleared (dismiss CaptureGuide) ---
      if (eventType === 'captures_cleared') {
        setCapturePositions(null);
      }

      // --- Illegal change (blocking modal) ---
      if (eventType === 'illegal_change') {
        setIllegalChangeOpen(true);
      }

      // --- Board lost tracking (show modal after 10s) ---
      if (eventType === 'board_lost') {
        if (!boardLostActiveRef.current) {
          boardLostActiveRef.current = true;
          boardLostTimerRef.current = setTimeout(() => {
            setBoardLostOpen(true);
          }, BOARD_LOST_THRESHOLD_MS);
        }
      }

      // Any event that is not board_lost cancels the timer.
      if (eventType !== 'board_lost' && boardLostActiveRef.current) {
        boardLostActiveRef.current = false;
        if (boardLostTimerRef.current) {
          clearTimeout(boardLostTimerRef.current);
          boardLostTimerRef.current = null;
        }
        setBoardLostOpen(false);
      }
    }

    processedRef.current = syncEvents.length;
  }, [newEvents, syncEvents.length]);

  // Cleanup timer on unmount.
  useEffect(() => {
    return () => {
      if (boardLostTimerRef.current) clearTimeout(boardLostTimerRef.current);
    };
  }, []);

  return (
    <>
      {/* ---- Non-blocking toast ---- */}
      <Snackbar
        open={toastOpen}
        autoHideDuration={SNACKBAR_DURATION}
        onClose={closeToast}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
      >
        {toastConfig ? (
          <Alert
            severity={toastConfig.severity}
            icon={toastConfig.icon}
            onClose={closeToast}
            sx={{ width: '100%', fontSize: '1rem' }}
          >
            {toastConfig.message}
          </Alert>
        ) : undefined}
      </Snackbar>

      {/* ---- Capture guide (blocking) ---- */}
      {capturePositions && (
        <CaptureGuide positions={capturePositions} onDismiss={handleCaptureDismiss} />
      )}

      {/* ---- Illegal change dialog (blocking) ---- */}
      <Dialog open={illegalChangeOpen} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ textAlign: 'center' }}>棋盘状态异常</DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ textAlign: 'center', py: 1 }}>
            检测到棋盘发生非法变化，请选择操作。
          </Typography>
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', gap: 2, pb: 2 }}>
          <Button variant="contained" onClick={handleIllegalRestore}>
            恢复棋局
          </Button>
          <Button variant="outlined" onClick={handleIllegalIgnore}>
            忽略
          </Button>
        </DialogActions>
      </Dialog>

      {/* ---- Board lost dialog (blocking, after 10s) ---- */}
      <Dialog open={boardLostOpen} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ textAlign: 'center', color: 'error.main' }}>
          棋盘检测异常
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ textAlign: 'center', py: 1 }}>
            棋盘检测异常，请检查摄像头和棋盘位置
          </Typography>
        </DialogContent>
        <DialogActions sx={{ justifyContent: 'center', pb: 2 }}>
          <Button
            variant="contained"
            onClick={() => {
              setBoardLostOpen(false);
              boardLostActiveRef.current = false;
              onDismiss?.();
            }}
          >
            确定
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default VisionSyncOverlay;
