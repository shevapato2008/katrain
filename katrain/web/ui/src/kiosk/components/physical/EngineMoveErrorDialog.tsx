import { useEffect, useState } from 'react';
import { Button, CircularProgress, Dialog, DialogActions, DialogContent, DialogTitle, Snackbar, Typography } from '@mui/material';
import { useTranslation } from '../../../hooks/useTranslation';
import { API, type PhysicalEngineErrorState } from '../../../api';
import { formatGtpCoord } from '../../../utils/gtpCoord';

interface Props {
  error: PhysicalEngineErrorState | null;
  sessionId: string | null;
  token?: string;
  boardSize: number;
  // Task 8's awaiting-removal timeout re-prompt (a fresh object each time) — while the
  // dialog is in the 'waiting' phase, a change here briefly re-emphasizes the message.
  reminderTick?: unknown;
  onDismiss?: () => void; // best-effort parent-state clear (retry ok:true / stale-token 409)
  onResign: () => void; // reuse GamePage's existing resign-confirm flow (state D)
}

type Phase = 'error' | 'waiting';

/** Task 9: modal for a bounded-retry Golaxy engine-tunnel failure (B5/M1/M4 backend,
 * B4/M5/D8 retry/cancel endpoints). Visibility is driven by `error.recovery_token !==
 * dismissedToken` (a purely local guard) rather than the `error` prop's mere presence —
 * this lets the two outcomes with NO matching WS broadcast (retry ok:true, and a stale
 * 409) close the dialog immediately without waiting on (or requiring) a parent-state
 * round-trip, while a genuine `physical_engine_error_resolved` broadcast still closes it
 * via `error` itself going null (see useGameSession). */
const EngineMoveErrorDialog = ({ error, sessionId, token, boardSize, reminderTick, onDismiss, onResign }: Props) => {
  const { t } = useTranslation();
  const [phase, setPhase] = useState<Phase>('error');
  const [currentToken, setCurrentToken] = useState<string | null>(null);
  const [detail, setDetail] = useState('');
  const [busy, setBusy] = useState(false);
  const [dismissedToken, setDismissedToken] = useState<string | null>(null);
  const [expired, setExpired] = useState(false);
  const [emphasized, setEmphasized] = useState(false);
  // Retains the last non-null `error` so the Dialog's content stays renderable while it
  // plays its close transition (or right after `error` itself goes null, e.g. the
  // `physical_engine_error_resolved` broadcast) — the Snackbar below is intentionally
  // independent of this and of `error` entirely, so a stale-token 409's "已过期" notice
  // survives the very state-clear that closes the dialog.
  const [snapshot, setSnapshot] = useState<PhysicalEngineErrorState | null>(null);

  // A genuinely NEW broadcast (a new `error` object from useGameSession) resets local
  // state. Our own retry-failure/cancel updates below never recreate `error` (no parent
  // setter is called for those), so this can't loop or fight the phase transitions.
  useEffect(() => {
    if (!error) return;
    setSnapshot(error);
    setPhase('error');
    setCurrentToken(error.recovery_token);
    setDetail(error.detail);
  }, [error]);

  useEffect(() => {
    if (reminderTick === undefined || reminderTick === null || phase !== 'waiting') return;
    setEmphasized(true);
    const id = setTimeout(() => setEmphasized(false), 2000);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reminderTick]);

  const open = !!error && error.recovery_token !== dismissedToken;
  const display = error ?? snapshot;
  if (!display) return null;

  const coordLabel = formatGtpCoord(display.col, display.row, boardSize);

  const handleRetry = async () => {
    if (!sessionId || !currentToken || busy) return;
    setBusy(true);
    try {
      const res = await API.visionEngineMoveRetry(sessionId, currentToken, token);
      if (res.ok) {
        setDismissedToken(display.recovery_token);
        onDismiss?.();
      } else {
        setDetail(res.detail ?? '');
        if (res.recovery_token) setCurrentToken(res.recovery_token);
      }
    } catch {
      // 409 (stale/consumed token) or any other transport failure: the recovery episode
      // is gone server-side — closing without a resolvable token to retry is the only
      // sane outcome.
      setExpired(true);
      setDismissedToken(display.recovery_token);
      onDismiss?.();
    } finally {
      setBusy(false);
    }
  };

  const handleCancel = async () => {
    if (!sessionId || !currentToken || busy) return;
    setBusy(true);
    try {
      const res = await API.visionEngineMoveCancel(sessionId, currentToken, token);
      if (res.ok) setPhase('waiting');
    } catch {
      setExpired(true);
      setDismissedToken(display.recovery_token);
      onDismiss?.();
    } finally {
      setBusy(false);
    }
  };

  const handleResign = () => {
    setDismissedToken(display.recovery_token);
    onResign();
  };

  return (
    <>
      <Dialog open={open} maxWidth="xs" fullWidth>
        {phase === 'error' ? (
          <>
            <DialogTitle>{t('Golaxy connection error', '星阵连接出错')}</DialogTitle>
            <DialogContent>
              <Typography variant="body2">
                {t('Move at {coord} failed to submit', '落子 {coord} 提交失败').replace('{coord}', coordLabel)}
                {' · '}
                {t('Attempts', '已重试')} {display.attempts}
              </Typography>
              {detail && (
                <Typography variant="caption" color="error" sx={{ display: 'block', mt: 1 }}>
                  {detail}
                </Typography>
              )}
            </DialogContent>
            <DialogActions>
              <Button onClick={handleRetry} variant="contained" disabled={busy}>
                {busy ? <CircularProgress size={16} color="inherit" /> : t('Retry', '重试')}
              </Button>
              <Button onClick={handleCancel} color="warning" disabled={busy}>
                {t('Remove the physical stone', '拿回棋子')}
              </Button>
              <Button onClick={handleResign} color="error" disabled={busy}>
                {t('Resign', '认输')}
              </Button>
            </DialogActions>
          </>
        ) : (
          <>
            <DialogTitle>{t('Waiting for stone removal', '等待拿回棋子')}</DialogTitle>
            <DialogContent sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CircularProgress size={20} />
              <Typography variant="body2" color={emphasized ? 'warning.main' : 'text.primary'}>
                {t('Please remove the stone at {coord}', '请拿回 {coord} 处的棋子').replace('{coord}', coordLabel)}
              </Typography>
            </DialogContent>
          </>
        )}
      </Dialog>
      <Snackbar
        open={expired}
        autoHideDuration={4000}
        onClose={() => setExpired(false)}
        anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
        message={t('This recovery request has expired', '该恢复请求已过期')}
      />
    </>
  );
};

export default EngineMoveErrorDialog;
