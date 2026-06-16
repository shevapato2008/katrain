import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  Box, Typography, Button, Chip, CircularProgress,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
} from '@mui/material';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import LiveBoard from '../../components/live/LiveBoard';
import { useTranslation } from '../../hooks/useTranslation';
import {
  BaipuAPI, getCachedSgf, saveProgress, getProgress, clearProgress,
  canonToBoard, canonToGtp, type BaipuStep, type BaipuMeta,
} from '../../api/baipuApi';
import { LedAPI, type LedColor } from '../../api/ledApi';

const stoneToLedColor = (c: 'B' | 'W'): LedColor => (c === 'B' ? 'black' : 'white');

type Phase = 'loading' | 'guiding' | 'await_removal' | 'done' | 'error';

const HealthDot = ({ label, ok }: { label: string; ok: boolean | null }) => (
  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
    <Box sx={{ width: 9, height: 9, borderRadius: '50%', bgcolor: ok == null ? '#666' : ok ? '#34c759' : '#ff3b30' }} />
    <Typography variant="caption" sx={{ color: 'text.secondary' }}>{label}</Typography>
  </Box>
);

const PlayerPanel = ({ color, name, active, t }: { color: 'B' | 'W'; name: string; active: boolean; t: (k: string, d?: string) => string }) => (
  <Box
    data-testid={`baipu-player-${color}`}
    data-active={active ? 'true' : 'false'}
    sx={{
      display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.25, borderRadius: '10px',
      border: active ? '2px solid' : '1px solid',
      borderColor: active ? 'primary.main' : 'rgba(255,255,255,0.12)',
      bgcolor: active ? 'rgba(92,181,122,0.12)' : 'rgba(255,255,255,0.04)',
    }}
  >
    <Box sx={{ width: 18, height: 18, borderRadius: '50%', bgcolor: color === 'B' ? '#1a1a1a' : '#e8e4df', border: '1px solid rgba(255,255,255,0.25)' }} />
    <Typography variant="body2" noWrap sx={{ fontWeight: active ? 700 : 400 }}>{name || (color === 'B' ? t('Black', '黑方') : t('White', '白方'))}</Typography>
    {active && <Chip size="small" label={t('to place', '落子中')} color="primary" sx={{ height: 20 }} />}
  </Box>
);

/**
 * 摆谱 session: a DUMB player of backend `steps[]` (decision ②). The frontend
 * never computes captures — it plays back what `/baipu/load` returned.
 *
 * State machine (decision ③④; QA + 带灯拍 are no-ops in P1, wired in P2/P4):
 *   guiding(k): highlight steps[k] on screen (+ LED in P2); user places the stone
 *     └ 确认 → if steps[k].removed → await_removal(k) else advance
 *   await_removal(k): flash the captured stones; user removes them physically
 *     └ 已移除 → advance
 *   advance: k++ ; pass steps auto-advance ; k==N → done
 *   撤回上一手: physical-guided single-step undo
 *   退出: guarded (confirm dialog)
 *
 * Coordinates from the backend are canonical (row=0 top); we convert to
 * LiveBoard's y=0-bottom convention at the rendering boundary.
 */
const BaipuSessionPage = () => {
  const { source = '' } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [phase, setPhase] = useState<Phase>('loading');
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<BaipuStep[]>([]);
  const [boardSize, setBoardSize] = useState(19);
  const [meta, setMeta] = useState<BaipuMeta | null>(null);
  const [k, setK] = useState(0); // steps applied to the physical board
  const [exitOpen, setExitOpen] = useState(false);
  const [undoOpen, setUndoOpen] = useState(false);
  const [resumePrompt, setResumePrompt] = useState<number | null>(null);
  const [ledOk, setLedOk] = useState<boolean | null>(null); // null = unknown / not enabled

  // Resolve SGF: fresh navigation state first, then the offline localStorage cache.
  const sgf = useMemo(() => {
    const navSgf = (location.state as { sgf?: string } | null)?.sgf;
    if (navSgf) return navSgf;
    return getCachedSgf(source)?.sgf ?? null;
  }, [location.state, source]);

  // Load per-step truth from the backend engine. (The "no SGF" case is rendered
  // directly below — no effect-driven setState needed.)
  useEffect(() => {
    if (!sgf) return;
    let cancelled = false;
    BaipuAPI.load({ sgf })
      .then((resp) => {
        if (cancelled) return;
        setSteps(resp.steps);
        setBoardSize(resp.board_size);
        setMeta(resp.meta);
        const prog = getProgress(source);
        if (prog && prog.k > 0 && prog.k < resp.steps.length) {
          setResumePrompt(prog.k); // ask continue vs restart
        }
        setPhase('guiding');
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
        setPhase('error');
      });
    return () => { cancelled = true; };
  }, [sgf, source]);

  const currentStep: BaipuStep | undefined = steps[k];

  // Build LiveBoard inputs from canonical steps.
  const moves = useMemo(
    () => steps.map((s) => (s.kind === 'pass' || s.row == null || s.col == null ? 'pass' : canonToGtp(s.row, s.col, boardSize))),
    [steps, boardSize],
  );
  const stoneColors = useMemo(() => steps.map((s) => (s.color ?? 'B') as 'B' | 'W'), [steps]);

  const advance = useCallback(() => {
    setK((prev) => {
      const next = prev + 1;
      saveProgress(source, { k: next, frames: 0, updatedAt: Date.now() });
      setPhase(next >= steps.length ? 'done' : 'guiding');
      return next;
    });
  }, [source, steps.length]);

  // Pass steps require no physical action — auto-advance (plan §1.3).
  useEffect(() => {
    if (phase === 'guiding' && currentStep && currentStep.kind === 'pass') {
      const timer = setTimeout(advance, 500);
      return () => clearTimeout(timer);
    }
  }, [phase, currentStep, advance]);

  // Drive the LED board to mirror the on-screen guidance (UI-tolerant path:
  // failures only gray out the health dot, they never block placement).
  useEffect(() => {
    if (phase === 'guiding' && currentStep && currentStep.kind !== 'pass' && currentStep.row != null && currentStep.col != null && currentStep.color) {
      LedAPI.point({ row: currentStep.row, col: currentStep.col, color: stoneToLedColor(currentStep.color) })
        .then((r) => setLedOk(r.connected))
        .catch(() => setLedOk(false));
    } else if (phase === 'await_removal' && currentStep && currentStep.removed.length > 0) {
      LedAPI.points(currentStep.removed.map((p) => ({ row: p.row, col: p.col, color: 'remove' as LedColor })))
        .then((r) => setLedOk(r.connected))
        .catch(() => setLedOk(false));
    } else if (phase === 'done') {
      LedAPI.clear().then((r) => setLedOk(r.connected)).catch(() => setLedOk(false));
    }
  }, [phase, k, currentStep]);

  // Blackout the LED when leaving the session.
  useEffect(() => () => { LedAPI.clear().catch(() => undefined); }, []);

  const relight = () => {
    if (currentStep && currentStep.kind !== 'pass' && currentStep.row != null && currentStep.col != null && currentStep.color) {
      LedAPI.point({ row: currentStep.row, col: currentStep.col, color: stoneToLedColor(currentStep.color) })
        .then((r) => setLedOk(r.connected))
        .catch(() => setLedOk(false));
    }
  };

  const handleConfirm = () => {
    if (!currentStep) return;
    if (currentStep.removed.length > 0) {
      setPhase('await_removal');
    } else {
      advance();
    }
  };

  const handleUndo = () => {
    setUndoOpen(false);
    setK((prev) => {
      const next = Math.max(0, prev - 1);
      saveProgress(source, { k: next, frames: 0, updatedAt: Date.now() });
      return next;
    });
    setPhase('guiding');
  };

  const handleExit = () => {
    setExitOpen(false);
    navigate('/kiosk/baipu');
  };

  // --- guidance overlays (convert canonical -> LiveBoard y=0 bottom) ---
  const nextMovePoint = useMemo(() => {
    if ((phase !== 'guiding' && phase !== 'await_removal') || !currentStep) return null;
    if (currentStep.kind === 'pass' || currentStep.row == null || currentStep.col == null) return null;
    return { ...canonToBoard(currentStep.row, currentStep.col, boardSize), color: (currentStep.color ?? 'B') as 'B' | 'W' };
  }, [phase, currentStep, boardSize]);

  const capturedPositions = useMemo(() => {
    if (phase !== 'await_removal' || !currentStep) return null;
    return currentStep.removed.map((p) => canonToBoard(p.row, p.col, boardSize));
  }, [phase, currentStep, boardSize]);

  // During await_removal keep the board at k (captured stones still visible);
  // otherwise show steps[0..k-1].
  const currentMove = k;

  const nextColor = currentStep?.color ?? null;
  const nextColorLabel = nextColor === 'B' ? t('Black', '黑') : nextColor === 'W' ? t('White', '白') : '';
  const ledColorLabel = nextColor === 'B' ? t('red LED', '红灯') : nextColor === 'W' ? t('green LED', '绿灯') : '';

  if (!sgf || phase === 'error') {
    return (
      <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: 2 }}>
        <Typography color="error">{error ?? t('No SGF found for this session', '未找到该会话的棋谱')}</Typography>
        <Button variant="contained" onClick={() => navigate('/kiosk/baipu')}>{t('Back', '返回')}</Button>
      </Box>
    );
  }

  if (phase === 'loading') {
    return (
      <Box sx={{ height: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Persistent dashboard status bar — the screen is the instrument, the board is the subject. */}
      <Box
        data-testid="baipu-status-bar"
        sx={{
          display: 'flex', alignItems: 'center', gap: 2, px: 3, py: 1.5,
          bgcolor: '#1a1a1a', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 700 }}>
          {phase === 'done'
            ? t('Done', '已完成')
            : <>{t('Place', '落子')} <Box component="span" sx={{ color: 'primary.main' }}>{nextColorLabel}</Box></>}
        </Typography>
        <Chip
          data-testid="baipu-progress"
          label={`${t('Move', '第')} ${Math.min(k + (phase === 'done' ? 0 : 1), steps.length)}/${steps.length} ${t('moves', '手')}`}
          sx={{ bgcolor: 'rgba(255,255,255,0.08)', fontFamily: '"IBM Plex Mono", monospace' }}
        />
        <Typography variant="caption" sx={{ color: 'text.secondary' }}>
          {t('Captured', '已采集')} 0 {t('frames', '帧')}
        </Typography>
        <Box sx={{ flex: 1 }} />
        <HealthDot label="LED" ok={ledOk} />
        <HealthDot label={t('Camera', '相机')} ok={null} />
      </Box>

      <Box sx={{ flex: 1, display: 'flex', minHeight: 0 }}>
        {/* Board */}
        <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', bgcolor: '#0f0f0f', minHeight: 0, p: 1 }}>
          <LiveBoard
            moves={moves}
            stoneColors={stoneColors}
            currentMove={currentMove}
            boardSize={boardSize}
            showCoordinates
            nextMovePoint={nextMovePoint}
            capturedPositions={capturedPositions}
          />
        </Box>

        {/* Right rail: players + next-color chip + controls */}
        <Box sx={{ width: 280, display: 'flex', flexDirection: 'column', gap: 2, p: 2, borderLeft: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
          <PlayerPanel color="B" name={meta?.player_black ?? ''} active={nextColor === 'B' && phase !== 'done'} t={t} />
          <PlayerPanel color="W" name={meta?.player_white ?? ''} active={nextColor === 'W' && phase !== 'done'} t={t} />

          {/* Most salient element: the next stone color = LED color */}
          {phase !== 'done' && nextColor && (
            <Box
              data-testid="baipu-next-chip"
              sx={{
                mt: 1, p: 2, borderRadius: '12px', textAlign: 'center',
                bgcolor: nextColor === 'B' ? 'rgba(255,59,48,0.14)' : 'rgba(52,199,89,0.14)',
                border: `2px solid ${nextColor === 'B' ? '#ff3b30' : '#34c759'}`,
              }}
            >
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{t('Next stone', '下一手')}</Typography>
              <Typography variant="h5" sx={{ fontWeight: 800 }}>{nextColorLabel}</Typography>
              <Typography variant="caption" sx={{ color: 'text.secondary' }}>{ledColorLabel}</Typography>
            </Box>
          )}

          <Box sx={{ flex: 1 }} />

          {/* Primary action */}
          {phase === 'guiding' && currentStep?.kind !== 'pass' && (
            <Button
              fullWidth variant="contained" onClick={handleConfirm} data-testid="baipu-confirm"
              sx={{ minHeight: 88, fontSize: '1.3rem', borderRadius: '12px', fontWeight: 700 }}
            >
              {t('Confirm', '确认落子')}
            </Button>
          )}
          {phase === 'guiding' && currentStep?.kind === 'pass' && (
            <Typography variant="body2" sx={{ textAlign: 'center', color: 'text.secondary' }}>{t('Pass — continuing…', '虚手，继续…')}</Typography>
          )}
          {phase === 'await_removal' && (
            <Button
              fullWidth variant="contained" color="warning" onClick={advance} data-testid="baipu-removed"
              sx={{ minHeight: 88, fontSize: '1.2rem', borderRadius: '12px', fontWeight: 700 }}
            >
              {t('Removed', '已移除')} {currentStep?.removed.length} {t('stones', '子')}
            </Button>
          )}
          {phase === 'done' && (
            <Button fullWidth variant="contained" onClick={() => navigate('/kiosk/baipu')} data-testid="baipu-done-back" sx={{ minHeight: 64, borderRadius: '12px' }}>
              {t('Done — back to list', '完成，返回列表')}
            </Button>
          )}

          {/* Secondary controls (session-level kept away from the per-move primary) */}
          {phase === 'guiding' && currentStep?.kind !== 'pass' && (
            <Button variant="text" onClick={relight} data-testid="baipu-relight" sx={{ color: 'text.secondary' }}>
              {t('Re-light', '重新点灯')}
            </Button>
          )}
          <Box sx={{ display: 'flex', gap: 1 }}>
            <Button fullWidth variant="outlined" disabled={k === 0 || phase === 'done'} onClick={() => setUndoOpen(true)} data-testid="baipu-undo" sx={{ borderRadius: '10px' }}>
              {t('Undo', '撤回上一手')}
            </Button>
            <Button variant="text" color="inherit" onClick={() => setExitOpen(true)} data-testid="baipu-exit" sx={{ color: 'text.secondary', minWidth: 64 }}>
              {t('Exit', '退出')}
            </Button>
          </Box>
        </Box>
      </Box>

      {/* 提子 independent mode: full-width banner to break the place→confirm rhythm */}
      {phase === 'await_removal' && (
        <Box
          data-testid="baipu-removal-banner"
          sx={{ px: 3, py: 1.5, bgcolor: 'rgba(47,111,255,0.18)', borderTop: '2px solid #2f6fff', textAlign: 'center', flexShrink: 0 }}
        >
          <Typography variant="h6" sx={{ fontWeight: 700 }}>
            {t('Remove the captured stones (flashing)', '请移除被提的子（闪烁处）')} — {currentStep?.removed.length}
          </Typography>
        </Box>
      )}

      {/* Resume prompt */}
      <Dialog open={resumePrompt !== null} onClose={() => setResumePrompt(null)}>
        <DialogTitle>{t('Continue last session?', '继续上次会话？')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('You were at move', '上次进行到第')} {resumePrompt} {t('moves', '手')}。
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => { clearProgress(source); setK(0); setResumePrompt(null); }}>{t('Restart', '重新开始')}</Button>
          <Button variant="contained" onClick={() => { if (resumePrompt != null) setK(resumePrompt); setResumePrompt(null); }} data-testid="baipu-resume-continue">
            {t('Continue', '继续上次')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Undo confirm (physical-guided) */}
      <Dialog open={undoOpen} onClose={() => setUndoOpen(false)}>
        <DialogTitle>{t('Undo last move?', '撤回上一手？')}</DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('Physically remove the last stone you placed (and restore any captured stones), then confirm.', '请从棋盘上拿掉刚摆的子（并恢复被提的子），然后确认。')}
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setUndoOpen(false)}>{t('Cancel', '取消')}</Button>
          <Button variant="contained" color="warning" onClick={handleUndo}>{t('Undone', '已撤回')}</Button>
        </DialogActions>
      </Dialog>

      {/* Exit confirm */}
      <Dialog open={exitOpen} onClose={() => setExitOpen(false)}>
        <DialogTitle>{t('Exit placement?', '退出摆谱？')}</DialogTitle>
        <DialogContent>
          <DialogContentText>{t('Your progress is saved and can be resumed.', '进度已保存，可稍后继续。')}</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setExitOpen(false)}>{t('Cancel', '取消')}</Button>
          <Button variant="contained" onClick={handleExit}>{t('Exit', '退出')}</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default BaipuSessionPage;
