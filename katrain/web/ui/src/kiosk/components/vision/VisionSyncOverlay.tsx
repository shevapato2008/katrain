import { useState, useEffect, useRef, useCallback } from 'react';
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
import { useVoice, type VoiceName } from '../../hooks/useVoice';
import {
  initialRecoveryState,
  reduceRecoveryState,
  type PendingStone,
  type RecoveryState,
} from './visionRecovery';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface VisionSyncOverlayProps {
  syncEvents: VisionSyncEvent[];
  onDismiss?: () => void;
  sessionId: string | null;
  boardSize: number;
  playerToMove: string | null;
  currentNodeId: number | null;
  /** Human stone already sent to a remote platform; its local game record has
   * not advanced yet, so the same-cell camera diff is expected until the reply. */
  platformPendingStone?: PendingStone | null;
  /** Board-loss precedence (Task B1.4, wired from GamePage.tsx): true while a
   * higher-priority board-loss surface (the escalation dialog or the recalibration
   * modal) is already up, so this generic "board detection abnormal" dialog never
   * stacks on top of / behind it. Default false — unrelated call sites are unaffected. */
  suppressBoardLost?: boolean;
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

const VisionSyncOverlay = ({ syncEvents, onDismiss, sessionId, boardSize, playerToMove, currentNodeId, platformPendingStone = null, suppressBoardLost = false }: VisionSyncOverlayProps) => {
  const { t } = useTranslation();
  const { speak, stop } = useVoice();

  // -- Toast state ----------------------------------------------------------
  const [toastOpen, setToastOpen] = useState(false);
  const [toastConfig, setToastConfig] = useState<ToastConfig | null>(null);

  const [recovery, setRecovery] = useState<RecoveryState>(initialRecoveryState);
  const spokenRecoveryRef = useRef<string | null>(null);
  const stoneRecovery = recovery.blocking?.kind === 'stone' ? recovery.blocking : null;
  const recoveryVoiceName: VoiceName | null = stoneRecovery
    ? stoneRecovery.unbacked ? 'stone_offcenter' : 'suspected_move'
    : null;
  const recoveryVoiceIdentity = stoneRecovery && recoveryVoiceName
    ? `${recoveryVoiceName}:${stoneRecovery.row}:${stoneRecovery.col}:${stoneRecovery.from?.[0] ?? '-'}:${stoneRecovery.from?.[1] ?? '-'}`
    : null;

  // -- Modal: board_lost (>10s persistent) ----------------------------------
  const [boardLostOpen, setBoardLostOpen] = useState(false);
  const boardLostTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const boardLostActiveRef = useRef(false);
  const boardLostPersistentRef = useRef(false);

  // `useVisionSync` trims history to 100 items, so an array index is not stable.
  const lastProcessedSeqRef = useRef(-1);
  const currentNodeIdRef = useRef(currentNodeId);

  // -- Close helpers --------------------------------------------------------
  const closeToast = useCallback(() => setToastOpen(false), []);

  // -- Board mismatch dialog callbacks ---------------------------------------
  const handleAdoptObserved = useCallback((x: number, y: number) => {
    if (sessionId) API.playMove(sessionId, { x, y }).catch(() => undefined);
    setRecovery((state) => ({ ...state, blocking: null }));
  }, [sessionId]);

  const handleMismatchRestored = useCallback(() => {
    API.visionResetSync().catch(() => undefined);
    setRecovery((state) => ({ ...state, blocking: null }));
  }, []);

  const handleMismatchDismiss = useCallback(() => {
    setRecovery((state) => ({ ...state, blocking: null }));
  }, []);

  // -- Ambiguous move card callbacks -----------------------------------------
  const handleAmbiguousConfirm = useCallback((x: number, y: number) => {
    if (sessionId) API.playMove(sessionId, { x, y }).catch(() => undefined);
    setRecovery((state) => ({ ...state, blocking: null }));
  }, [sessionId]);

  const handleAmbiguousIgnore = useCallback(() => {
    // 「不是落子」= 用户作证那一格没有子。把那一格此刻的像素存成否认样本,只要它还长成
    // 那样就不再被识别成子;像素一变(用户真把子放上去)标签当场失效。
    //
    // 这取代了原来的 adopt='physical'。那条路是把**假阳性收进基线当成现实**,而且
    // RESET_SYNC 会顺手销毁参考帧 —— 等于用户每按一次「忽略」,就把唯一能按像素否决
    // 反光的那套证据毁掉一次,下一颗假阳性畅通无阻。
    //
    // 摆偏那一档(unbacked)不否认:那儿**确实有子**,只是没放正,按钮说的是「我挪一下」。
    // 把它记成「这儿没有子」会在用户挪正之后反过来压住那颗真子。
    if (recovery.blocking?.kind === 'stone' && !recovery.blocking.unbacked) {
      API.visionDenyStone(recovery.blocking.row, recovery.blocking.col).catch(() => undefined);
    }
    setRecovery((state) => ({ ...state, blocking: null }));
  }, [recovery.blocking]);

  useEffect(() => {
    if (currentNodeIdRef.current === currentNodeId) return;
    currentNodeIdRef.current = currentNodeId;
    setRecovery((state) => reduceRecoveryState(state, { kind: 'node_advanced' }));
  }, [currentNodeId]);

  useEffect(() => {
    if (recoveryVoiceIdentity === null || recoveryVoiceName === null) {
      if (spokenRecoveryRef.current !== null) stop();
      spokenRecoveryRef.current = null;
      return;
    }
    if (spokenRecoveryRef.current === recoveryVoiceIdentity) return;

    spokenRecoveryRef.current = recoveryVoiceIdentity;
    speak(recoveryVoiceName);
  }, [recoveryVoiceIdentity, recoveryVoiceName, speak, stop]);

  // -- Process new events ---------------------------------------------------
  useEffect(() => {
    const newEvents = syncEvents.filter((event) => event.seq > lastProcessedSeqRef.current);
    if (newEvents.length === 0) return;

    const nowMs = Date.now();
    setRecovery((state) => newEvents.reduce(
      (next, event) => reduceRecoveryState(next, { kind: 'vision_event', event, nowMs, platformPendingStone }),
      state,
    ));

    for (const event of newEvents) {
      const eventType = event.type;

      // --- Toast events (non-blocking) ---
      // Only acknowledge recovery from a loss long enough to need intervention.
      // Ordinary short occlusions recover silently; duplicate events cannot start
      // a new toast after the loss episode has ended.
      if (eventType in TOAST_MAP && (eventType !== 'board_reacquired' || boardLostPersistentRef.current)) {
        const config = TOAST_MAP[eventType]!;
        setToastConfig(config);
        setToastOpen(true);
      }

      // --- Board lost tracking (show modal after 10s) ---
      if (eventType === 'board_lost') {
        if (!boardLostActiveRef.current) {
          boardLostActiveRef.current = true;
          boardLostPersistentRef.current = false;
          boardLostTimerRef.current = setTimeout(() => {
            boardLostPersistentRef.current = true;
            setBoardLostOpen(true);
          }, BOARD_LOST_THRESHOLD_MS);
        }
      }

      // Only a sync result from a readable board ends the loss episode. Move
      // candidates and other independent worker messages do not prove recovery.
      const boardReadable = eventType === 'board_reacquired' || eventType === 'synced'
        || eventType === 'illegal_change' || eventType === 'capture_pending'
        || eventType === 'captures_cleared' || eventType === 'setup_progress'
        || eventType === 'setup_complete';
      if (boardReadable && boardLostActiveRef.current) {
        boardLostActiveRef.current = false;
        boardLostPersistentRef.current = false;
        if (boardLostTimerRef.current) {
          clearTimeout(boardLostTimerRef.current);
          boardLostTimerRef.current = null;
        }
        setBoardLostOpen(false);
      }
    }

    lastProcessedSeqRef.current = Math.max(...newEvents.map((event) => event.seq));
  }, [syncEvents, platformPendingStone]);

  useEffect(() => {
    if (!recovery.pending) return;
    const delay = Math.max(0, recovery.pending.expiresAt - Date.now());
    const timer = setTimeout(() => {
      setRecovery((state) => reduceRecoveryState(state, {
        kind: 'pending_deadline',
        nowMs: Date.now(),
      }));
    }, delay);
    return () => clearTimeout(timer);
  }, [recovery.pending]);

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
      {recovery.blocking?.kind === 'capture' && (
        <CaptureGuide positions={recovery.blocking.positions} />
      )}

      {/* ---- Board mismatch dialog (blocking, diff + restore checklist) ---- */}
      {recovery.blocking?.kind === 'mismatch' && (
        <BoardMismatchDialog
          open
          positions={recovery.blocking.positions}
          missing={recovery.blocking.missing}
          boardSize={boardSize}
          playerToMove={playerToMove}
          onAdoptObserved={handleAdoptObserved}
          onRestored={handleMismatchRestored}
          onDismiss={handleMismatchDismiss}
        />
      )}

      {/* ---- Ambiguous move confirmation card ---- */}
      {recovery.blocking?.kind === 'stone' && (
        <AmbiguousMoveCard
          row={recovery.blocking.row}
          col={recovery.blocking.col}
          boardSize={boardSize}
          color={recovery.blocking.color}
          unbacked={recovery.blocking.unbacked}
          from={recovery.blocking.from}
          onConfirm={handleAmbiguousConfirm}
          onIgnore={handleAmbiguousIgnore}
        />
      )}

      {/* ---- Board lost dialog (blocking, after 10s) ----
          suppressBoardLost short-circuits visibility only — the 10s timer/state machine
          above keeps running so it reflects reality once the higher-priority surface clears. */}
      {boardLostOpen && !suppressBoardLost && recovery.blocking === null && (
        <Dialog open maxWidth="xs" fullWidth>
          <DialogTitle sx={{ textAlign: 'center', color: 'error.main' }}>
            棋盘检测异常
          </DialogTitle>
          <DialogContent>
            <Typography variant="body1" sx={{ textAlign: 'center', py: 1 }}>
              棋盘检测异常，请检查摄像头和棋盘位置
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center' }}>
              {t('vision:board_lost_hint', '看一下摄像头有没有被挡住、棋盘有没有被挪动；挪动过的话要重新标定')}
            </Typography>
          </DialogContent>
          <DialogActions sx={{ justifyContent: 'center', pb: 2 }}>
            <Button
              variant="contained"
              onClick={() => {
                setBoardLostOpen(false);
                onDismiss?.();
              }}
            >
              确定
            </Button>
          </DialogActions>
        </Dialog>
      )}
    </>
  );
};

export default VisionSyncOverlay;
