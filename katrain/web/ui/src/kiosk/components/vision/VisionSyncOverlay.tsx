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
import BoardMismatchDialog from '../physical/BoardMismatchDialog';
import AmbiguousMoveCard from '../physical/AmbiguousMoveCard';
import { API } from '../../../api';
import { useTranslation } from '../../../hooks/useTranslation';
import type { VisionSyncEvent, SyncEventType } from '../../hooks/useVisionSync';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Pos = [number, number, number]; // [row, col, color]

interface MismatchState {
  positions: Pos[];
  missing: Pos[];
}

interface AmbiguousState {
  row: number;
  col: number;
}

interface VisionSyncOverlayProps {
  syncEvents: VisionSyncEvent[];
  onDismiss?: () => void;
  sessionId: string | null;
  boardSize: number;
  playerToMove: string | null;
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
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const VisionSyncOverlay = ({ syncEvents, onDismiss, sessionId, boardSize, playerToMove }: VisionSyncOverlayProps) => {
  const { t } = useTranslation();

  // -- Toast state ----------------------------------------------------------
  const [toastOpen, setToastOpen] = useState(false);
  const [toastConfig, setToastConfig] = useState<ToastConfig | null>(null);

  // -- Modal: capture_pending -----------------------------------------------
  const [capturePositions, setCapturePositions] = useState<
    Array<{ row: number; col: number; color: number }> | null
  >(null);

  // -- Dialog: illegal_change (board mismatch diff) --------------------------
  const [mismatch, setMismatch] = useState<MismatchState | null>(null);

  // -- Card: ambiguous_stone --------------------------------------------------
  const [ambiguous, setAmbiguous] = useState<AmbiguousState | null>(null);

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

  const handleCaptureDismiss = useCallback(() => {
    setCapturePositions(null);
  }, []);

  // -- Board mismatch dialog callbacks ---------------------------------------
  const handleAdoptObserved = useCallback((x: number, y: number) => {
    if (sessionId) API.playMove(sessionId, { x, y }).catch(() => undefined);
    setMismatch(null);
  }, [sessionId]);

  const handleMismatchRestored = useCallback(() => {
    API.visionResetSync().catch(() => undefined);
    setMismatch(null);
  }, []);

  const handleMismatchDismiss = useCallback(() => {
    setMismatch(null);
  }, []);

  // -- Ambiguous move card callbacks -----------------------------------------
  const handleAmbiguousConfirm = useCallback((x: number, y: number) => {
    if (sessionId) API.playMove(sessionId, { x, y }).catch(() => undefined);
    setAmbiguous(null);
  }, [sessionId]);

  const handleAmbiguousIgnore = useCallback(() => {
    // Ignore = accept the current physical board as the baseline (adopt='physical'),
    // keeping the ignored stone in the detector baseline so it doesn't re-fire. (The
    // trust-digital recovery path would re-push the digital board and re-detect it.)
    API.visionResetSync('physical').catch(() => undefined);
    setAmbiguous(null);
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

      // --- Illegal change (board mismatch diff dialog) ---
      if (eventType === 'illegal_change') {
        const positions = (event.data.positions as Pos[] | undefined) ?? [];
        const missing = (event.data.missing as Pos[] | undefined) ?? [];
        setMismatch({ positions, missing });
      }

      // --- Board restored to a synced state (auto-dismiss mismatch) ---
      if (eventType === 'synced') {
        setMismatch(null);
      }

      // --- Ambiguous stone (confirmation card) ---
      if (eventType === 'ambiguous_stone') {
        const { row, col } = event.data as { row: number; col: number };
        setAmbiguous({ row, col });
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

      {/* ---- Board mismatch dialog (blocking, diff + restore checklist) ---- */}
      <BoardMismatchDialog
        open={!!mismatch}
        positions={mismatch?.positions ?? []}
        missing={mismatch?.missing ?? []}
        boardSize={boardSize}
        playerToMove={playerToMove}
        onAdoptObserved={handleAdoptObserved}
        onRestored={handleMismatchRestored}
        onDismiss={handleMismatchDismiss}
      />

      {/* ---- Ambiguous move confirmation card ---- */}
      {ambiguous && (
        <AmbiguousMoveCard
          row={ambiguous.row}
          col={ambiguous.col}
          boardSize={boardSize}
          onConfirm={handleAmbiguousConfirm}
          onIgnore={handleAmbiguousIgnore}
        />
      )}

      {/* ---- Board lost dialog (blocking, after 10s) ---- */}
      <Dialog open={boardLostOpen} maxWidth="xs" fullWidth>
        <DialogTitle sx={{ textAlign: 'center', color: 'error.main' }}>
          棋盘检测异常
        </DialogTitle>
        <DialogContent>
          <Typography variant="body1" sx={{ textAlign: 'center', py: 1 }}>
            棋盘检测异常，请检查摄像头和棋盘位置
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center' }}>
            {t('If the board was bumped, use Re-align in the banner', '若棋盘被碰动，请使用横幅中的「重新定位」')}
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
