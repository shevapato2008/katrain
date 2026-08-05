import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box, Typography, Button, IconButton, LinearProgress, CircularProgress,
  Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions,
  Snackbar, Alert,
} from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import ScienceIcon from '@mui/icons-material/Science';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';
import ReplayIcon from '@mui/icons-material/Replay';
import EditIcon from '@mui/icons-material/Edit';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardDoubleArrowLeftIcon from '@mui/icons-material/KeyboardDoubleArrowLeft';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import KeyboardDoubleArrowRightIcon from '@mui/icons-material/KeyboardDoubleArrowRight';

import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import Board from '../../components/Board';
import ResearchSetupPanel from '../components/research/ResearchSetupPanel';
import ResearchAnalysisPanel from '../components/research/ResearchAnalysisPanel';
import GameLibraryModal from '../components/research/CloudSGFPanel';
import { useResearchBoard, type ResearchBoardState } from '../hooks/useResearchBoard';
import { useResearchSession } from '../../hooks/useResearchSession';
import { useTranslation } from '../../hooks/useTranslation';
import { useImmersive } from '../context/ImmersiveContext';
import { useAuth } from '../../context/AuthContext';
import { API } from '../../api';
import { KifuAPI } from '../../api/kifuApi';
import { UserGamesAPI } from '../../api/userGamesApi';

// Minimal shape of a KataGo quick-analyze moveInfo entry (API.quickAnalyze returns `any`).
interface QuickAnalyzeMoveInfo {
  move: string;
  visits: number;
  winrate: number;
  scoreLead?: number;
}

// Shared "immersive top bar" back-button chrome (Analyzing/Report/Failure views).
const topBarBackSx = {
  width: 34, height: 34, minWidth: 34, minHeight: 34, borderRadius: '10px',
  border: '1px solid', borderColor: 'divider', bgcolor: 'background.paper',
  flexShrink: 0,
};

function StatBlock({ value, label }: { value: string; label: string }) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25, alignItems: 'center', minWidth: 80 }}>
      <Typography sx={{ color: 'text.primary', fontWeight: 700, fontSize: '0.95rem', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </Typography>
      <Typography sx={{ color: 'text.secondary', fontSize: '0.78rem' }}>{label}</Typography>
    </Box>
  );
}

// Format ETA seconds → "N分SS秒" / "N秒" (galaxy L546-550 verbatim math, extracted for reuse).
function formatEtaValue(etaSeconds: number, t: (key: string, fallback: string) => string): string {
  if (etaSeconds >= 60) {
    return t('research:time_min_sec', '{min}分{sec}秒')
      .replace('{min}', String(Math.floor(etaSeconds / 60)))
      .replace('{sec}', (etaSeconds % 60).toString().padStart(2, '0'));
  }
  return t('research:time_sec', '{sec}秒').replace('{sec}', String(etaSeconds));
}

const ResearchPage = () => {
  const [searchParams] = useSearchParams();
  const { t } = useTranslation();
  const { setImmersive } = useImmersive();
  const { token } = useAuth();

  // ── Board state hook (L1: edit/setup) ──
  const board = useResearchBoard();

  // ── View state machine (Step 2) ──
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisProgress, setAnalysisProgress] = useState<{ analyzed: number; total: number } | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [confirmLeaveOpen, setConfirmLeaveOpen] = useState(false);
  const analysisComplete = analysisProgress !== null && analysisProgress.total > 0 && analysisProgress.analyzed >= analysisProgress.total;
  const frozenSnapshot = useRef<ResearchBoardState | null>(null);
  const activeSessionIdRef = useRef<string | null>(null);
  const pollFailRef = useRef(0);
  const analysisStartRef = useRef<{ time: number; analyzed: number } | null>(null);
  const hintsEnabledRef = useRef(false);
  const [etaSeconds, setEtaSeconds] = useState<number | null>(null);

  // Game library modal (从棋谱库打开)
  const [libraryOpen, setLibraryOpen] = useState(false);

  // Kiosk 19-only clamp toast: fires whenever a loaded SGF declared a non-19 size
  // (useResearchBoard force-holds the board at 19 and surfaces this via lastLoadClamped).
  // Derived during render (no effect needed) — `dismissedClampSize` tracks which
  // clamped load the user has already dismissed, so re-showing after a NEW clamped
  // load just means lastLoadedSize no longer matches the dismissed one.
  const [dismissedClampSize, setDismissedClampSize] = useState<number | null | undefined>(undefined);
  const clampToastOpen = board.lastLoadClamped && board.lastLoadedSize !== dismissedClampSize;

  // Stone placement sound for L1 (galaxy L57-72 verbatim, minus portrait concerns)
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const prevMoveRef = useRef<number>(0);
  useEffect(() => {
    if (board.currentMove !== prevMoveRef.current) {
      prevMoveRef.current = board.currentMove;
      if (!isAnalyzing) {
        if (!audioRef.current) {
          audioRef.current = new Audio('/assets/sounds/stone1.wav');
        }
        const audio = audioRef.current;
        audio.currentTime = 0;
        audio.play().catch(() => {});
      }
    }
  }, [board.currentMove, isAnalyzing]);

  // L1 quick analysis: hints + territory (galaxy L74-141 verbatim)
  const [l1ShowHints, setL1ShowHints] = useState(false);
  const [l1ShowTerritory, setL1ShowTerritory] = useState(false);
  const [l1AiMarkers, setL1AiMarkers] = useState<AiMoveMarker[] | null>(null);
  const [l1Ownership, setL1Ownership] = useState<number[][] | null>(null);
  const [l1AnalysisPending, setL1AnalysisPending] = useState(false);
  const l1AnalysisKeyRef = useRef<string>('');

  const l1PositionKey = useMemo(() => {
    return `${board.boardSize}-${board.komi}-${board.rules}-${board.currentMove}-${board.moves.slice(0, board.currentMove).join(',')}`;
  }, [board.boardSize, board.komi, board.rules, board.currentMove, board.moves]);

  useEffect(() => {
    if (isAnalyzing) return; // report/analyzing views handle their own analysis
    // No setState here when both toggles are off: `l1AiMarkers`/`l1Ownership` are
    // already display-gated at the call sites below (`aiMarkers={l1ShowHints ? … :
    // null}`, and LiveBoard itself only draws `ownership` when `showTerritory` is
    // true — see boardUtils' `if (showTerritory && ownership …)`), so stale state
    // here is inert; clearing it would just be a synchronous setState-in-effect
    // with no observable effect.
    if (!l1ShowHints && !l1ShowTerritory) return;
    const key = l1PositionKey;
    l1AnalysisKeyRef.current = key;
    // Marks the upcoming quick-analyze fetch (below) as pending — the fetch itself is
    // asynchronous, matching the precedent in kiosk/context/VisionContext.tsx.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setL1AnalysisPending(true);

    const movesUpToCurrent = board.moves.slice(0, board.currentMove);
    const colors = board.stoneColors.slice(0, board.currentMove);
    const kataMoves = movesUpToCurrent.map((m, i) => [colors[i], m]);

    API.quickAnalyze({
      moves: kataMoves,
      board_size: board.boardSize,
      komi: board.komi,
      rules: board.rules,
      max_visits: 200,
    }, token ?? undefined).then((result) => {
      if (l1AnalysisKeyRef.current !== key) return; // stale
      const turnResult = result?.turnInfos?.[0] ?? result;
      const moveInfos: QuickAnalyzeMoveInfo[] = turnResult?.moveInfos ?? [];
      const markers: AiMoveMarker[] = moveInfos.slice(0, 5).map((mi, idx: number) => ({
        move: mi.move,
        rank: idx + 1,
        visits: mi.visits,
        winrate: mi.winrate,
        score_lead: mi.scoreLead ?? 0,
      }));
      setL1AiMarkers(markers);

      const rawOwnership = turnResult?.ownership;
      if (rawOwnership && Array.isArray(rawOwnership)) {
        const size = board.boardSize;
        const grid: number[][] = [];
        for (let y = 0; y < size; y++) {
          grid.push(rawOwnership.slice(y * size, (y + 1) * size));
        }
        setL1Ownership(grid);
      }
    }).catch((err) => {
      console.error('Quick analysis failed:', err);
    }).finally(() => {
      if (l1AnalysisKeyRef.current === key) setL1AnalysisPending(false);
    });
  }, [l1ShowHints, l1ShowTerritory, l1PositionKey, isAnalyzing, token]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleL1ToggleHints = useCallback(() => setL1ShowHints(prev => !prev), []);
  const handleL1ToggleTerritory = useCallback(() => setL1ShowTerritory(prev => !prev), []);

  // ── Research session hook (analyzing / report) ──
  const session = useResearchSession();

  const [analysisToggles, setAnalysisToggles] = useState<Record<string, boolean>>({
    hints: false,
    ownership: false,
    policy: false,
    eval: false,
    numbers: false,
    children: false,
    coords: true,
  });

  const toggleAnalysis = useCallback((key: string) => {
    setAnalysisToggles(prev => ({ ...prev, [key]: !prev[key] }));
  }, []);

  // Derive winrate/scoreLead from gameState analysis root (galaxy L287-295 verbatim)
  const analysisData = useMemo(() => {
    const gs = session.gameState;
    if (!gs?.analysis) return { winrate: 0.5, scoreLead: 0 };
    return {
      winrate: gs.analysis.winrate ?? 0.5,
      scoreLead: gs.analysis.score ?? 0,
    };
  }, [session.gameState]);

  // Step 3: immersive drives off isAnalyzing (hide Dock for analyzing/report only)
  useEffect(() => { setImmersive(isAnalyzing); return () => setImmersive(false); }, [isAnalyzing, setImmersive]);

  // Step 3: leak-guard — keepalive DELETE keyed on session.sessionId (deps re-run so the
  // CURRENT id is captured). Do NOT use a []-dep destroySession() cleanup: it captures
  // sessionId===null and no-ops (Codex #9).
  useEffect(() => {
    const cleanup = () => {
      if (session.sessionId) fetch(`/api/session/${session.sessionId}`, { method: 'DELETE', keepalive: true }).catch(() => {});
    };
    window.addEventListener('beforeunload', cleanup);
    return () => { window.removeEventListener('beforeunload', cleanup); cleanup(); };
  }, [session.sessionId]);

  // Step 4: freeze L1 → serialize → createSession(skipAnalysis) → analysisScan(500)
  const handleStartAnalysis = useCallback(async () => {
    frozenSnapshot.current = board.getSnapshot();
    const { sgf } = board.serializeToSGF();
    const sgfToLoad = board.moves.length > 0 ? sgf : undefined;
    const newSessionId = await session.createSession(sgfToLoad, { skipAnalysis: true, initialMove: board.currentMove });
    if (!newSessionId) {
      setAnalysisError(t('research:session_failed', '无法创建研究会话，请重试'));
      setIsAnalyzing(true);
      return;
    }
    activeSessionIdRef.current = newSessionId;
    setAnalysisProgress(null);
    setEtaSeconds(null);
    setAnalysisError(null);
    analysisStartRef.current = null;
    hintsEnabledRef.current = false;
    pollFailRef.current = 0;
    setIsAnalyzing(true);
    try {
      await API.analysisScan(newSessionId, 500);
    } catch {
      setAnalysisError(t('research:scan_failed', '启动分析失败，请重试'));
    }
  }, [board, session, t]);

  // Step 5: poll analysis progress; guard on !analysisError; trip failure after 5 consecutive
  // poll errors (state D).
  useEffect(() => {
    if (!isAnalyzing || analysisComplete || analysisError) return;
    const sid = activeSessionIdRef.current;
    if (!sid) return;

    const interval = setInterval(async () => {
      try {
        const progress = await API.analysisProgress(sid);
        pollFailRef.current = 0;
        if (activeSessionIdRef.current === sid) {
          setAnalysisProgress({ analyzed: progress.analyzed, total: progress.total });

          const now = Date.now();
          if (progress.analyzed > 0 && progress.total > 0) {
            if (!analysisStartRef.current || analysisStartRef.current.analyzed === 0) {
              analysisStartRef.current = { time: now, analyzed: progress.analyzed };
            } else {
              const elapsed = (now - analysisStartRef.current.time) / 1000;
              const done = progress.analyzed - analysisStartRef.current.analyzed;
              if (done > 0 && elapsed > 2) {
                const rate = done / elapsed;
                const remaining = progress.total - progress.analyzed;
                setEtaSeconds(Math.round(remaining / rate));
              }
            }
          }
        }
      } catch {
        pollFailRef.current += 1;
        if (pollFailRef.current >= 5) setAnalysisError(t('research:engine_unresponsive', '引擎无响应，已保留已完成结果'));
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [isAnalyzing, analysisComplete, analysisError]); // eslint-disable-line react-hooks/exhaustive-deps

  // Only handleReturnToEdit (返回编辑) destroys the session. Declared before
  // handleRetryAnalysis (below) — the react-hooks/react-compiler lint rules treat a
  // forward-reference to a not-yet-declared component-scope const as an error even
  // inside a closure (the reference only resolves at call-time, after mount, but the
  // linter can't see that), so the declaration order here is load-bearing for `npm
  // run lint`, not just a style choice.
  const handleReturnToEdit = useCallback(async () => {
    activeSessionIdRef.current = null;
    await session.destroySession();
    if (frozenSnapshot.current) {
      board.restoreSnapshot(frozenSnapshot.current);
      frozenSnapshot.current = null;
    }
    setIsAnalyzing(false);
    setAnalysisProgress(null);
    setEtaSeconds(null);
    setAnalysisError(null);
    analysisStartRef.current = null;
    hintsEnabledRef.current = false;
    setAnalysisToggles(prev => ({ ...prev, hints: false, ownership: false, policy: false }));
  }, [session, board]);

  // Step 6: retry re-calls analysisScan on the SAME live session (incremental resume —
  // _do_analysis_scan only queues !analysis_exists). Do NOT destroySession on failure.
  // Deps are deliberately [t] only (not handleReturnToEdit) — see the comment above
  // handleReturnToEdit for why the ordering matters; the identity staleness here is
  // intentional/inert (activeSessionIdRef is a ref, read fresh on every call).
  // eslint-disable-next-line react-hooks/preserve-manual-memoization
  const handleRetryAnalysis = useCallback(async () => {
    const sid = activeSessionIdRef.current;
    if (!sid) { await handleReturnToEdit(); return; }
    setAnalysisError(null);
    pollFailRef.current = 0;
    analysisStartRef.current = null;
    try {
      await API.analysisScan(sid, 500);
    } catch {
      setAnalysisError(t('research:scan_failed', '启动分析失败，请重试'));
    }
  }, [t]); // eslint-disable-line react-hooks/exhaustive-deps

  // When analysis completes, navigate to the last move to get full state and enable hints
  // (galaxy L240-252 verbatim).
  useEffect(() => {
    if (analysisComplete && session.gameState && !hintsEnabledRef.current) {
      hintsEnabledRef.current = true;
      const gs = session.gameState;
      const currentNodeId = gs.history[gs.current_node_index]?.node_id;
      if (currentNodeId !== undefined) {
        session.onNavigate(currentNodeId);
      }
      // One-shot "analysis just completed" transition, ref-guarded (hintsEnabledRef) so it
      // fires exactly once; not a derived-render value (also drives the session.toggleHints()
      // side effect below).
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setAnalysisToggles(prev => ({ ...prev, hints: true }));
      session.toggleHints();
    }
  }, [analysisComplete, session.gameState]); // eslint-disable-line react-hooks/exhaustive-deps

  // Report-view navigation — use node_id from history for direct jumps (galaxy L396-406 verbatim)
  const handleL2MoveChange = useCallback(async (move: number) => {
    if (!session.gameState) return;
    const history = session.gameState.history;
    const clampedMove = Math.max(0, Math.min(history.length - 1, move));
    if (clampedMove === session.gameState.current_node_index) return;

    const targetNodeId = history[clampedMove]?.node_id;
    if (targetNodeId !== undefined) {
      await session.onNavigate(targetNodeId);
    }
  }, [session]);

  // Cloud/library load: open modal / load selected SGF into L1
  const handleOpenFromCloud = useCallback(() => setLibraryOpen(true), []);
  const handleLoadFromLibrary = useCallback((sgf: string) => {
    board.loadFromSGF(sgf);
  }, [board]);

  // Step 9: ?kifu_id deep link. Do NOT re-derive the SGF from `board` here — board's state
  // update from loadFromSGF() below hasn't flushed within this same async continuation, so
  // board.moves/currentMove would still read the pre-load (empty) values. That's exactly
  // galaxy's stale-closure bug (ResearchPage.tsx:187-199): its [searchParams] effect closed
  // over handleStartAnalysis from the empty-board render, so serializeToSGF() read stale
  // moves and createSession(undefined, …) silently no-op'd. Sidestep it entirely by passing
  // the JUST-FETCHED album.sgf_content straight into createSession.
  const kifuLoadedRef = useRef(false);
  useEffect(() => {
    const kifuId = searchParams.get('kifu_id');
    if (!kifuId || kifuLoadedRef.current) return;
    kifuLoadedRef.current = true;

    KifuAPI.getAlbum(Number(kifuId))
      .then(async (album) => {
        if (album.sgf_content) {
          const result = board.loadFromSGF(album.sgf_content);
          if (!result.success) {
            console.error('Failed to load kifu for deep link:', result.error);
            return;
          }
        }
        if (album.player_black) board.setPlayerBlack(album.player_black);
        if (album.player_white) board.setPlayerWhite(album.player_white);

        if (searchParams.get('analyze') === '1' && album.sgf_content) {
          const newSessionId = await session.createSession(album.sgf_content, { skipAnalysis: true });
          if (!newSessionId) {
            setAnalysisError(t('research:session_failed', '无法创建研究会话，请重试'));
            setIsAnalyzing(true);
            return;
          }
          activeSessionIdRef.current = newSessionId;
          setAnalysisProgress(null);
          setEtaSeconds(null);
          setAnalysisError(null);
          analysisStartRef.current = null;
          hintsEnabledRef.current = false;
          pollFailRef.current = 0;
          setIsAnalyzing(true);
          try {
            await API.analysisScan(newSessionId, 500);
          } catch {
            setAnalysisError(t('research:scan_failed', '启动分析失败，请重试'));
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load kifu for deep link:', err);
      });
  }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

  // Task 7(a): 复盘本局 — GamePage's EndgameCard hands off the just-finished game's SGF via
  // sessionStorage (no query param, since the game just ended in-app). Ref-guarded so it
  // fires exactly once per mount; the key is removed immediately so a later remount (e.g.
  // navigating away and back) doesn't reload it.
  const reviewSgfLoadedRef = useRef(false);
  useEffect(() => {
    if (reviewSgfLoadedRef.current) return;
    // The 对局历史 deep link (?user_game_id, effect below) owns loading in that flow —
    // don't also replay a live-SGF handoff, or both would race to seed the board.
    if (searchParams.get('user_game_id')) return;
    const sgf = sessionStorage.getItem('kioskReviewSgf');
    if (!sgf) return;
    reviewSgfLoadedRef.current = true;
    sessionStorage.removeItem('kioskReviewSgf');
    board.loadFromSGF(sgf);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Task 7(b): 对局历史 一键复盘 — ?user_game_id=X (&analyze=1) deep link into a recorded
  // local game (Task 4's shared UserGamesAPI). Same stale-closure trap as ?kifu_id= above:
  // thread the FETCHED detail.sgf_content straight into createSession, never re-derive from
  // `board` in this same async continuation. Ref-guarded; waits for `token` (auth loads
  // asynchronously) before firing.
  const userGameLoadedRef = useRef(false);
  useEffect(() => {
    const userGameId = searchParams.get('user_game_id');
    if (!userGameId || userGameLoadedRef.current || !token) return;
    userGameLoadedRef.current = true;

    UserGamesAPI.get(token, userGameId)
      .then(async (detail) => {
        if (!detail.sgf_content) return;
        board.loadFromSGF(detail.sgf_content);

        if (searchParams.get('analyze') === '1') {
          const newSessionId = await session.createSession(detail.sgf_content, { skipAnalysis: true });
          if (!newSessionId) {
            setAnalysisError(t('research:session_failed', '无法创建研究会话，请重试'));
            setIsAnalyzing(true);
            return;
          }
          activeSessionIdRef.current = newSessionId;
          setAnalysisProgress(null);
          setEtaSeconds(null);
          setAnalysisError(null);
          analysisStartRef.current = null;
          hintsEnabledRef.current = false;
          pollFailRef.current = 0;
          setIsAnalyzing(true);
          try {
            await API.analysisScan(newSessionId, 500);
          } catch {
            setAnalysisError(t('research:scan_failed', '启动分析失败，请重试'));
          }
        }
      })
      .catch((err) => {
        console.error('Failed to load user game for deep link:', err);
      });
  }, [searchParams, token]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 8: local confirm dialog (replaces galaxy's useGameNavigation) ──
  const confirmDialog = (
    <Dialog open={confirmLeaveOpen} onClose={() => setConfirmLeaveOpen(false)} maxWidth="xs" fullWidth>
      <DialogTitle>{t('research:cancel_analysis_title', '取消分析？')}</DialogTitle>
      <DialogContent>
        <DialogContentText>{t('research:cancel_analysis_warning', '分析正在进行中，确定要取消吗？')}</DialogContentText>
      </DialogContent>
      <DialogActions>
        <Button onClick={() => setConfirmLeaveOpen(false)} color="inherit">
          {t('research:continue_analysis', '继续分析')}
        </Button>
        <Button
          onClick={() => { setConfirmLeaveOpen(false); handleReturnToEdit(); }}
          color="error"
          variant="contained"
        >
          {t('research:cancel_and_leave', '取消并离开')}
        </Button>
      </DialogActions>
    </Dialog>
  );

  const clampSnackbar = (
    <Snackbar
      open={clampToastOpen}
      autoHideDuration={4000}
      onClose={() => setDismissedClampSize(board.lastLoadedSize)}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
    >
      <Alert severity="warning" onClose={() => setDismissedClampSize(board.lastLoadedSize)}>
        {t('research:only_19_supported', '仅支持 19 路，已按 19 路加载')}
      </Alert>
    </Snackbar>
  );

  const libraryModal = (
    <GameLibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} onLoadGame={handleLoadFromLibrary} />
  );

  // ──────────────────────────── Step 7: render precedence (four views) ────────────────────────────

  // D. Failure — artifact research-states.html state D
  if (isAnalyzing && analysisError) {
    return (
      <>
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default' }}>
          <Box sx={{ height: 52, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 1.75, px: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}>
            <IconButton onClick={handleReturnToEdit} sx={topBarBackSx}>
              <ArrowBackIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
            </IconButton>
            <Typography variant="body2" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.75 }}>
              {t('research:mode', '研究')}
              <Box component="span" sx={{ color: 'text.disabled' }}>›</Box>
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>{t('research:ai_analysis', 'AI 分析')}</Box>
            </Typography>
          </Box>
          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, textAlign: 'center', px: 4 }}>
            <Box sx={{
              width: 78, height: 78, borderRadius: '50%', display: 'grid', placeItems: 'center',
              background: 'radial-gradient(circle at 50% 42%, rgba(226,104,92,.2), transparent 70%)',
            }}>
              <ErrorOutlineIcon sx={{ fontSize: 40, color: 'error.main' }} />
            </Box>
            <Typography variant="h5" sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500 }}>
              {t('research:analysis_failed', '分析失败')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 420 }}>
              {analysisError}
            </Typography>
            <Box sx={{ display: 'flex', gap: 1.5, mt: 0.5 }}>
              <Button
                variant="contained"
                startIcon={<ReplayIcon />}
                onClick={handleRetryAnalysis}
                sx={{ bgcolor: 'primary.main', color: '#0d1a13', fontWeight: 700, '&:hover': { bgcolor: 'primary.dark' } }}
              >
                {t('research:retry_analysis', '重试分析')}
              </Button>
              <Button
                variant="outlined"
                onClick={handleReturnToEdit}
                sx={{ borderColor: 'divider', color: 'text.secondary' }}
              >
                {t('research:return_to_edit', '返回编辑')}
              </Button>
            </Box>
          </Box>
        </Box>
        {confirmDialog}
      </>
    );
  }

  // ③ Report — artifact research-flow.html state ③
  if (isAnalyzing && analysisComplete && session.gameState) {
    const gs = session.gameState;
    const totalMoves = gs.history.length - 1; // exclude root
    const currentMoveIdx = gs.current_node_index;

    return (
      <>
        <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
          <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: 'background.default', minWidth: 0 }}>
            <Box sx={{ height: 52, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 1.75, px: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}>
              <IconButton onClick={handleReturnToEdit} sx={topBarBackSx}>
                <ArrowBackIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
              </IconButton>
              <Typography variant="body2" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.75, flexWrap: 'wrap' }}>
                {t('research:mode', '研究')}
                <Box component="span" sx={{ color: 'text.disabled' }}>›</Box>
                {t('research:analysis_report', '分析报告')}
                <Box component="span" sx={{ color: 'text.disabled' }}>›</Box>
                <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>
                  {t('research:move_n', '第 {n} 手').replace('{n}', String(currentMoveIdx))}
                </Box>
              </Typography>
              <Button
                size="small"
                startIcon={<EditIcon sx={{ fontSize: 15 }} />}
                onClick={handleReturnToEdit}
                sx={{
                  ml: 'auto', color: 'primary.main', bgcolor: 'var(--raise2)', border: '1px solid',
                  borderColor: 'var(--raise2)', borderRadius: '20px', px: 1.75, fontSize: '0.8rem',
                }}
              >
                {t('research:return_to_edit', '返回编辑')}
              </Button>
            </Box>

            <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 0.5, minWidth: 0 }}>
              <Board
                gameState={gs}
                onMove={session.onMove}
                analysisToggles={analysisToggles}
              />
            </Box>
          </Box>

          <ResearchAnalysisPanel
            playerBlack={gs.players_info?.B?.name || board.playerBlack || t('research:black', '黑方')}
            playerWhite={gs.players_info?.W?.name || board.playerWhite || t('research:white', '白方')}
            currentMove={currentMoveIdx}
            totalMoves={totalMoves}
            onMoveChange={handleL2MoveChange}
            winrate={analysisData.winrate}
            scoreLead={analysisData.scoreLead}
            rules={board.rules}
            komi={board.komi}
            handicap={board.handicap}
            boardSize={board.boardSize}
            showMoveNumbers={analysisToggles.numbers}
            onToggleMoveNumbers={() => toggleAnalysis('numbers')}
            onPass={session.onPass}
            editMode={null}
            onEditModeChange={() => {}}
            placeMode="alternate"
            onPlaceModeChange={() => {}}
            showHints={analysisToggles.hints}
            onToggleHints={() => {
              toggleAnalysis('hints');
              session.toggleHints();
            }}
            showTerritory={analysisToggles.ownership}
            onToggleTerritory={() => {
              toggleAnalysis('ownership');
              session.toggleOwnership();
            }}
            onClear={() => {}}
            onOpen={board.openLocalSGF}
            onSave={board.saveLocalSGF}
            onCopyToClipboard={board.copyToClipboard}
            onOpenFromCloud={handleOpenFromCloud}
            analysisMoves={gs.analysis?.moves}
            history={gs.history}
            playerToMove={gs.player_to_move}
            children={gs.children}
          />
        </Box>
        {confirmDialog}
        {libraryModal}
        {clampSnackbar}
      </>
    );
  }

  // ② Analyzing — artifact research-flow.html state ②
  if (isAnalyzing) {
    const progressPercent = analysisProgress && analysisProgress.total > 0
      ? Math.round((analysisProgress.analyzed / analysisProgress.total) * 100)
      : 0;

    return (
      <>
        <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%', bgcolor: 'background.default' }}>
          <Box sx={{ height: 52, flexShrink: 0, display: 'flex', alignItems: 'center', gap: 1.75, px: 2.5, borderBottom: '1px solid', borderColor: 'divider' }}>
            <IconButton onClick={() => setConfirmLeaveOpen(true)} sx={topBarBackSx}>
              <ArrowBackIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
            </IconButton>
            <Typography variant="body2" sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center', gap: 0.75 }}>
              {t('research:mode', '研究')}
              <Box component="span" sx={{ color: 'text.disabled' }}>›</Box>
              <Box component="span" sx={{ color: 'text.primary', fontWeight: 600 }}>{t('research:analyzing_title', 'AI 分析中')}</Box>
            </Typography>
          </Box>

          <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 2, textAlign: 'center', px: 4 }}>
            <Box sx={{
              position: 'relative', width: 98, height: 98, borderRadius: '50%', display: 'grid', placeItems: 'center',
              background: 'radial-gradient(circle at 50% 42%, rgba(88,181,122,.22), transparent 70%)',
            }}>
              <CircularProgress size={98} thickness={2} disableShrink sx={{ position: 'absolute', color: 'primary.main' }} />
              <ScienceIcon sx={{ fontSize: 44, color: 'primary.main' }} />
            </Box>
            <Typography variant="h5" sx={{ fontFamily: "'Newsreader','Noto Serif SC',serif", fontWeight: 500 }}>
              {t('research:analyzing_game', '正在分析全局')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 440 }}>
              {t('research:analyzing_lede', 'KataGo 正逐手计算胜率、目差与最佳应手。分析在后台运行，你可以随时取消并回到编辑。')}
            </Typography>
            <Box sx={{ width: 440, maxWidth: '82%' }}>
              <LinearProgress
                variant={analysisProgress ? 'determinate' : 'indeterminate'}
                value={progressPercent}
                sx={{
                  height: 8, borderRadius: 5, bgcolor: 'var(--raise2)',
                  '& .MuiLinearProgress-bar': { borderRadius: 5, bgcolor: 'primary.main' },
                }}
              />
            </Box>
            {analysisProgress && (
              <Box sx={{ display: 'flex', gap: 4 }}>
                <StatBlock
                  value={`${analysisProgress.analyzed} / ${analysisProgress.total}`}
                  label={t('research:analyzed_moves', '已分析手数')}
                />
                <StatBlock value={`${progressPercent}%`} label={t('research:progress', '进度')} />
                <StatBlock
                  value={etaSeconds !== null && etaSeconds > 0 ? formatEtaValue(etaSeconds, t) : '—'}
                  label={t('research:eta_label', '预计剩余')}
                />
              </Box>
            )}
            <Button
              size="small"
              onClick={handleReturnToEdit}
              startIcon={<CloseIcon sx={{ fontSize: 16 }} />}
              sx={{
                mt: 0.5, bgcolor: 'background.paper', border: '1px solid', borderColor: 'divider',
                color: 'text.secondary', borderRadius: '12px', px: 2.5,
              }}
            >
              {t('research:cancel_to_edit', '取消分析，回到编辑')}
            </Button>
          </Box>
        </Box>
        {confirmDialog}
      </>
    );
  }

  // ① Edit — artifact research-flow.html state ①
  return (
    <>
      <Box sx={{ display: 'flex', flexDirection: 'row', height: '100%', overflow: 'hidden' }}>
        <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', bgcolor: 'background.default', minWidth: 0, minHeight: 0 }}>
          {/* minHeight:0 + overflow:hidden: without them this flex child grows to the board's
              intrinsic content size (~600px) and overflows/clips under the Dock instead of
              shrinking to the bounded content area. */}
          <Box sx={{ flexGrow: 1, minHeight: 0, overflow: 'hidden', display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
            <LiveBoard
              moves={board.moves}
              stoneColors={board.stoneColors}
              currentMove={board.currentMove}
              boardSize={board.boardSize}
              showCoordinates={true}
              showMoveNumbers={board.showMoveNumbers}
              handicapCount={board.handicapCount}
              onIntersectionClick={board.handleIntersectionClick}
              nextColor={board.nextColor ?? undefined}
              aiMarkers={l1ShowHints ? l1AiMarkers : null}
              showAiMarkers={l1ShowHints}
              showTerritory={l1ShowTerritory}
              ownership={l1Ownership}
            />
          </Box>

          {/* Bottom move-navigation bar — preserves data-testid="move-navigation" */}
          <Box
            data-testid="move-navigation"
            sx={{
              px: 3, py: 1.5, bgcolor: 'background.paper', borderTop: '1px solid', borderColor: 'divider',
              display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 1,
            }}
          >
            <IconButton
              size="small"
              disabled={board.currentMove === 0}
              onClick={() => board.handleMoveChange(0)}
              sx={{ color: 'text.secondary' }}
            >
              <KeyboardDoubleArrowLeftIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              disabled={board.currentMove === 0}
              onClick={() => board.handleMoveChange(board.currentMove - 1)}
              sx={{ color: 'text.secondary' }}
            >
              <ChevronLeftIcon fontSize="small" />
            </IconButton>
            <Typography
              variant="body2"
              sx={{
                mx: 2, fontFamily: '"JetBrains Mono", monospace', color: 'text.secondary',
                minWidth: 80, textAlign: 'center',
              }}
            >
              {t('research:move_counter', '{current} / {total} 手')
                .replace('{current}', String(Math.max(0, board.currentMove - board.handicapCount)))
                .replace('{total}', String(board.moves.length - board.handicapCount))}
            </Typography>
            <IconButton
              size="small"
              disabled={board.currentMove >= board.moves.length}
              onClick={() => board.handleMoveChange(board.currentMove + 1)}
              sx={{ color: 'text.secondary' }}
            >
              <ChevronRightIcon fontSize="small" />
            </IconButton>
            <IconButton
              size="small"
              disabled={board.currentMove >= board.moves.length}
              onClick={() => board.handleMoveChange(board.moves.length)}
              sx={{ color: 'text.secondary' }}
            >
              <KeyboardDoubleArrowRightIcon fontSize="small" />
            </IconButton>
          </Box>
        </Box>

        <ResearchSetupPanel
          playerBlack={board.playerBlack}
          playerWhite={board.playerWhite}
          onPlayerBlackChange={board.setPlayerBlack}
          onPlayerWhiteChange={board.setPlayerWhite}
          rules={board.rules}
          onRulesChange={board.setRules}
          komi={board.komi}
          onKomiChange={board.setKomi}
          handicap={board.handicap}
          onHandicapChange={board.setHandicap}
          showMoveNumbers={board.showMoveNumbers}
          onToggleMoveNumbers={() => board.setShowMoveNumbers(!board.showMoveNumbers)}
          onPass={board.handlePass}
          editMode={board.editMode}
          onEditModeChange={board.setEditMode}
          placeMode={board.placeMode}
          onPlaceModeChange={board.setPlaceMode}
          showHints={l1ShowHints}
          onToggleHints={handleL1ToggleHints}
          showTerritory={l1ShowTerritory}
          onToggleTerritory={handleL1ToggleTerritory}
          isAnalysisPending={l1AnalysisPending}
          onClear={board.handleClear}
          onOpen={board.openLocalSGF}
          onSave={board.saveLocalSGF}
          onCopyToClipboard={board.copyToClipboard}
          onOpenFromCloud={handleOpenFromCloud}
          onStartAnalysis={handleStartAnalysis}
        />
      </Box>
      {confirmDialog}
      {libraryModal}
      {clampSnackbar}
    </>
  );
};

export default ResearchPage;
