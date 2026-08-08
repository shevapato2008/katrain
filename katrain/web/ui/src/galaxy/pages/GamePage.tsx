import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@mui/material';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import Board from '../../components/Board';
import type { BoardProps } from '../../components/Board';
import { useGameSession } from '../../hooks/useGameSession';
import RightSidebarPanel from '../components/game/RightSidebarPanel';
import { useSettings } from '../../context/SettingsContext';
import { useGameNavigation } from '../context/GameNavigationContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { translateResult } from '../../utils/resultTranslation';
import { isRankedGameType } from '../../features/aiLadder/gameType';
import { getAiLadderGameStatus } from '../../features/aiLadder/api';
import type { AiLadderGameLifecycle } from '../../features/aiLadder/types';
import { peekAiLadderBefore, useAiLadderSettlement } from '../../features/aiLadder/settlement';
import BoardPageShell from '../components/board/BoardPageShell';
import ModulePlate from '../components/layout/ModulePlate';
import AiLadderSettlementPanel from '../components/aiLadder/AiLadderSettlementPanel';

// Dynamically imported Board3D — loaded on first 3D toggle, then stays mounted
type Board3DComponent = React.ComponentType<BoardProps>;

const GamePage = () => {
    const { sessionId } = useParams();
    const [searchParams] = useSearchParams();
    const [resignError, setResignError] = useState<string | null>(null);
    const navigate = useNavigate();
    useSettings(); // Subscribe to translation changes for re-render
    const { t } = useTranslation();
    const { token, user } = useAuth();
    const { registerActiveGame, unregisterActiveGame } = useGameNavigation();
    const mode = searchParams.get('mode') || 'free';
    const routeIsRated = mode === 'rated';
    const identity = String(user?.id ?? user?.username ?? 'anonymous');
    const rankedGameId = searchParams.get('game_id')
        || (sessionId ? peekAiLadderBefore(sessionId, identity)?.gameId : undefined);
    const [remoteLifecycle, setRemoteLifecycle] = useState<AiLadderGameLifecycle | null>(null);
    const [lifecycleError, setLifecycleError] = useState(false);
    const [lifecycleRetry, setLifecycleRetry] = useState(0);

    // Dynamic Board3D import — loaded once, then cached
    const [Board3D, setBoard3D] = useState<Board3DComponent | null>(null);
    const board3dLoadingRef = useRef(false);

    const {
        sessionId: currentSessionId,
        setSessionId,
        gameState,
        setGameState,
        error,
        onMove,
        onNavigate,
        handleAction
    } = useGameSession({ token: token || undefined });
    const isRated = routeIsRated || isRankedGameType(gameState?.game_type);
    const settlementFeedback = useAiLadderSettlement(sessionId, gameState?.game_type, gameState?.end_result, token || undefined, identity);

    useEffect(() => {
        if (!routeIsRated || !rankedGameId || gameState?.end_result) return;
        const controller = new AbortController();
        let timer: ReturnType<typeof setTimeout> | undefined;
        const poll = async () => {
            try {
                const lifecycle = await getAiLadderGameStatus(rankedGameId, token || undefined, controller.signal);
                if (controller.signal.aborted) return;
                setLifecycleError(false);
                setRemoteLifecycle(lifecycle.state === 'active' ? null : lifecycle);
                if (lifecycle.state === 'active') timer = setTimeout(() => { void poll(); }, 5000);
            } catch {
                if (!controller.signal.aborted) setLifecycleError(true);
            }
        };
        void poll();
        return () => {
            controller.abort();
            if (timer) clearTimeout(timer);
        };
    }, [gameState?.end_result, lifecycleRetry, rankedGameId, routeIsRated, token]);

    const checkRankedStillActive = useCallback(async () => {
        if (!isRated || !rankedGameId) return !isRated;
        try {
            const lifecycle = await getAiLadderGameStatus(rankedGameId, token || undefined);
            setLifecycleError(false);
            if (lifecycle.state === 'active') return true;
            setRemoteLifecycle(lifecycle);
        } catch {
            setLifecycleError(true);
        }
        return false;
    }, [isRated, rankedGameId, token]);

    // Analysis Toggles State
    const [analysisToggles, setAnalysisToggles] = useState<Record<string, boolean>>(() => ({
        children: false,
        eval: false,
        hints: false,
        policy: false,
        ownership: false,
        coords: true,
        numbers: false,
        score: true,
        winrate: true,
        view3d: false,
        stoneDropEffect: false,
    }));

    // Load Board3D dynamically when first requested
    useEffect(() => {
        if (analysisToggles.view3d && !Board3D && !board3dLoadingRef.current) {
            board3dLoadingRef.current = true;
            import('../../components/Board3D').then(mod => {
                setBoard3D(() => mod.default);
            });
        }
    }, [analysisToggles.view3d, Board3D]);

    // Track move count for resetting hints after user move (Case 3)
    const prevMoveCountRef = useRef<number>(0);
    // Track if we're waiting for analysis to auto-show (Case 2)
    const waitingForAnalysisRef = useRef<boolean>(false);

    const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
    const [showResignConfirm, setShowResignConfirm] = useState(false);
    const [showCountConfirm, setShowCountConfirm] = useState(false);
    const [countResult, setCountResult] = useState<string | null>(null);
    const audioCache = useRef<Record<string, HTMLAudioElement>>({});

    // 升降级结算：what this game did to the player's rank. Asked for once, when

    // Sound playing callback
    const handlePlaySound = useCallback((soundName: string) => {
        if (!audioCache.current[soundName]) {
            audioCache.current[soundName] = new Audio(`/assets/sounds/${soundName}.wav`);
        }
        const audio = audioCache.current[soundName];
        audio.currentTime = 0;
        audio.play().catch(err => console.warn('Sound playback failed:', err));
    }, []);

    // Timeout handler - auto-forfeit when time runs out
    const handleTimeout = useCallback(async () => {
        // A ladder AI that refused to move still has a clock, and that clock still runs
        // out. Forfeiting it would end the game "won by the human" over a board the
        // engine never played on. The server refuses to score such a game either way
        // (server.py _settle_ladder_game), but the win must not appear on screen at all.
        if (gameState?.last_ladder_error) return;
        if (!gameState?.end_result) {
            console.log('Timer expired - triggering timeout');
            try { await handleAction('timeout'); } catch { /* hook error state is authoritative */ }
        }
    }, [gameState?.end_result, gameState?.last_ladder_error, handleAction]);

    useEffect(() => {
        if (sessionId && sessionId !== currentSessionId) {
            setSessionId(sessionId);
        }
    }, [sessionId, currentSessionId, setSessionId]);

    // Sync with gameState.ui_state if available
    // Note: 'hints' and 'numbers' are excluded because they're managed locally
    useEffect(() => {
        if (gameState?.ui_state) {
            setAnalysisToggles(prev => ({
                ...prev,
                policy: gameState.ui_state.show_policy,
                ownership: gameState.ui_state.show_ownership,
                coords: gameState.ui_state.show_coordinates,
            }));
        }
    }, [gameState]);

    // Case 3: Reset hints to unselected after user makes a move
    useEffect(() => {
        if (!gameState) return;
        const currentMoveCount = gameState.current_node_index;
        if (prevMoveCountRef.current > 0 && currentMoveCount > prevMoveCountRef.current) {
            // Move was made, reset hints
            setAnalysisToggles(prev => ({ ...prev, hints: false }));
            waitingForAnalysisRef.current = false;
        }
        prevMoveCountRef.current = currentMoveCount;
    }, [gameState?.current_node_index]);

    // Case 2: Auto-show hints when analysis arrives while waiting
    // When analysis arrives, stop waiting and ensure hints stay ON (selected/highlighted)
    // The board reads analysisToggles.hints to decide whether to show top3 markers
    useEffect(() => {
        if (waitingForAnalysisRef.current && gameState?.analysis?.moves?.length) {
            // Analysis arrived - stop blinking, hints stays ON (already true)
            // Board will auto-show top3 because hints is true and top_moves exist
            waitingForAnalysisRef.current = false;
            // Force re-render to ensure board picks up the hints=true + top_moves
            setAnalysisToggles(prev => ({ ...prev, hints: true }));
        }
    }, [gameState?.analysis?.moves]);

    // Register/unregister active game for sidebar navigation protection
    useEffect(() => {
        if (gameState && !gameState.end_result && !remoteLifecycle) {
            registerActiveGame(async () => {
                await handleAction('resign');
            });
        } else {
            unregisterActiveGame();
        }
        return () => unregisterActiveGame();
    }, [gameState?.end_result, remoteLifecycle, registerActiveGame, unregisterActiveGame, handleAction]);

    const handleToggleChange = (setting: string) => {
        if (setting === 'view3d') {
            setAnalysisToggles(prev => {
                const next = { ...prev, view3d: !prev.view3d };
                localStorage.setItem('katrain_view3d', String(next.view3d));
                return next;
            });
            return;
        }
        if (setting === 'hints') {
            const hasAnalysis = !!gameState?.analysis?.moves?.length;
            const currentlyOn = analysisToggles.hints;

            if (currentlyOn) {
                // Case 1: Turning off - always allow
                setAnalysisToggles(prev => ({ ...prev, hints: false }));
                waitingForAnalysisRef.current = false;
            } else {
                // Turning on
                if (hasAnalysis) {
                    // Case 1: Analysis available, just show
                    setAnalysisToggles(prev => ({ ...prev, hints: true }));
                } else {
                    // Case 2: No analysis yet, start waiting and blink
                    setAnalysisToggles(prev => ({ ...prev, hints: true }));
                    waitingForAnalysisRef.current = true;
                }
            }
        } else {
            setAnalysisToggles(prev => ({ ...prev, [setting]: !prev[setting] }));
        }
    };

    const handleActionWrapper = (action: string) => {
        if (remoteLifecycle) return;
        if (isRated && action === 'pass') {
            void (async () => {
                if (await checkRankedStillActive()) await handleAction(action);
            })();
            return;
        }
        if (action === 'resign') {
            if (!gameState?.end_result) {
                setShowResignConfirm(true);
            }
        } else if (action === 'count') {
            if (!gameState?.end_result) {
                setShowCountConfirm(true);
            }
        } else {
            void (async () => { try { await handleAction(action); } catch { /* surfaced by hook */ } })();
        }
    };

    const confirmCount = async () => {
        setShowCountConfirm(false);
        if (!sessionId) return;
        try {
            const response = await API.requestCount(sessionId, token || undefined);
            if (response.result) {
                setCountResult(response.result);
            }
            if (response.state) {
                setGameState(response.state);
            }
        } catch (e: any) {
            console.error("Count request failed:", e);
            alert(e.message || "Count request failed");
        }
    };

    const confirmResign = async () => {
        try {
            await handleAction('resign');
            setShowResignConfirm(false);
        } catch (error) {
            setResignError(error instanceof Error ? error.message : '认输失败，请重试');
        }
    };

    const handleLeaveRequest = () => {
        if (!gameState?.end_result) {
            setShowLeaveConfirm(true);
        } else {
            navigate(gameState?.game_type === 'ai_ladder_ranked' ? '/galaxy/play/ai?mode=rated' : '/galaxy/play/ai');
        }
    };

    const handleConfirmLeave = async () => {
        try {
            await handleAction('resign');
            setShowLeaveConfirm(false);
            navigate(gameState?.game_type === 'ai_ladder_ranked' ? '/galaxy/play/ai?mode=rated' : '/galaxy/play/ai');
        } catch (error) {
            setResignError(error instanceof Error ? error.message : '认输失败，请重试');
        }
    };

    // Determine which color the human player controls (if any)
    const humanColor: 'B' | 'W' | null = gameState?.players_info?.B?.player_type === 'player:human' ? 'B'
        : gameState?.players_info?.W?.player_type === 'player:human' ? 'W'
        : null;

    if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert></Box>;
    if (!gameState) return <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>;

    const handleRankedMove = async (x: number, y: number) => {
        if (remoteLifecycle || !(await checkRankedStillActive())) return;
        onMove(x, y);
    };
    const controlsGameState = remoteLifecycle ? { ...gameState, end_result: 'REMOTE_ENDED' } : gameState;
    const remoteFeedback = remoteLifecycle?.state === 'pending_settlement'
        ? { kind: 'pending' as const, message: '本局已在其他设备结束，正在结算' }
        : remoteLifecycle?.state === 'settled'
            ? {
                kind: remoteLifecycle.receipt.counted ? 'authoritative_complete' as const : 'not_counted' as const,
                message: remoteLifecycle.receipt.counted
                    ? '本局已在其他设备结束，结算已完成'
                    : '本局已在其他设备结束，结算已完成（本局不计入升降级）',
            }
            : null;

    const board = (
        <Box sx={{ width: '100%', height: '100%', display: 'grid', placeItems: 'center', minWidth: 0, minHeight: 0, pointerEvents: remoteLifecycle ? 'none' : 'auto' }}>
            <div style={{
                display: (analysisToggles.view3d && Board3D) ? 'none' : 'flex',
                width: '100%', height: '100%',
                justifyContent: 'center', alignItems: 'center'
            }}>
                <Board
                    gameState={gameState}
                    onMove={isRated ? handleRankedMove : onMove}
                    analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
                    playerColor={humanColor}
                />
            </div>
            {analysisToggles.view3d && Board3D && (
                <Board3D
                    gameState={gameState}
                    onMove={isRated ? handleRankedMove : onMove}
                    analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
                    playerColor={humanColor}
                />
            )}
            {analysisToggles.view3d && !Board3D && <CircularProgress />}
        </Box>
    );

    const controls = (embedded = false) => (
        <RightSidebarPanel
            gameState={controlsGameState}
            analysisToggles={analysisToggles}
            onToggleChange={handleToggleChange}
            onNavigate={onNavigate}
            onAction={handleActionWrapper}
            isRated={isRated}
            onTimeout={handleTimeout}
            onPlaySound={handlePlaySound}
            isAnalysisPending={analysisToggles.hints && !gameState.analysis?.moves?.length}
            embedded={embedded}
        />
    );

    return (
        <Box sx={{ display: 'flex', height: '100%', minHeight: 0, overflow: 'hidden', position: 'relative' }}>
            <Box sx={{ position: 'absolute', top: 12, left: '50%', transform: 'translateX(-50%)', zIndex: 100, minWidth: 320 }}>
                {/* The ladder AI refused to move (the engine cannot serve the seated rung at
                    its calibrated strength). No move is coming and the clock keeps running,
                    so say so — an empty board with a ticking opponent clock reads as
                    "still thinking". */}
                {gameState.last_ladder_error && !gameState.end_result && (
                    <Alert severity="warning" data-testid="ladder-stalled">
                        {t('ladder:engine_stalled', '阶梯引擎不可用，AI 无法落子 · 本局不计入升降级，请退出本局')}
                    </Alert>
                )}
                {resignError && <Alert severity="error" onClose={() => setResignError(null)}>{resignError}</Alert>}
                {lifecycleError && !remoteLifecycle && (
                    <Alert severity="warning" action={<Button color="inherit" size="small" onClick={() => setLifecycleRetry((value) => value + 1)}>重试</Button>}>
                        暂时无法确认本局状态，请重试
                    </Alert>
                )}
            </Box>
            {/* Leave Confirmation Dialog */}
            <Dialog open={showLeaveConfirm} onClose={() => setShowLeaveConfirm(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('leave_game_title', 'Leave Game?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('leave_game_warning', 'The game is still in progress. Leaving will resign the game. Are you sure?')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowLeaveConfirm(false)}>{t('cancel', 'Cancel')}</Button>
                    <Button onClick={handleConfirmLeave} color="error" variant="contained">{t('resign_and_exit', 'Resign & Exit')}</Button>
                </DialogActions>
            </Dialog>

            {/* Resign Confirmation Dialog */}
            <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('resign_game_title', 'Resign Game?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('resign_confirm_text', 'Are you sure you want to resign?')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowResignConfirm(false)}>{t('cancel', 'Cancel')}</Button>
                    <Button onClick={confirmResign} color="error" variant="contained">{t('RESIGN', 'Resign')}</Button>
                </DialogActions>
            </Dialog>

            {/* Count Confirmation Dialog */}
            <Dialog open={showCountConfirm} onClose={() => setShowCountConfirm(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('count_confirm_title', 'End Game by Counting?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('count_confirm_text', 'Calculate the final score to end the game.')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowCountConfirm(false)}>{t('cancel', 'Cancel')}</Button>
                    <Button onClick={confirmCount} color="primary" variant="contained">{t('COUNT', 'Count')}</Button>
                </DialogActions>
            </Dialog>


            {/* Count Result Dialog */}
            <Dialog open={!!countResult} onClose={() => setCountResult(null)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('Game Over', 'Game Over')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('game_end:count', 'Game ended by counting: {result}').replace('{result}', translateResult(countResult, t, gameState?.ruleset))}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCountResult(null)} variant="contained">{t('ok', 'OK')}</Button>
                </DialogActions>
            </Dialog>

            {isRated ? (
                <BoardPageShell
                    board={board}
                    modulePlate={(
                        <ModulePlate
                            title={t('rated_play', '升降级对弈')}
                            backLabel={t('rated_play_short', '升降级')}
                            backTo="/galaxy/play/ai?mode=rated"
                        />
                    )}
                    railBody={(
                        <>
                            {(gameState.end_result || remoteFeedback) && (
                                <AiLadderSettlementPanel
                                    feedback={remoteFeedback ?? settlementFeedback ?? { kind: 'pending', message: '正在读取服务器结算结果' }}
                                    onPlayAgain={() => navigate('/galaxy/play/ai?mode=rated')}
                                    onReturn={() => navigate('/galaxy/play')}
                                />
                            )}
                            {controls(true)}
                        </>
                    )}
                    actions={null}
                />
            ) : (<>
            {/* Main Area: Board only */}
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                {/* Header */}
                <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.3)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 3 }}>
                    <Typography variant="subtitle2" color="primary.main">
                        {t('play_vs_ai', 'Play vs AI')} ({mode})
                    </Typography>
                    <Button
                        size="small"
                        color="error"
                        variant="outlined"
                        startIcon={<ExitToAppIcon />}
                        onClick={handleLeaveRequest}
                        sx={{ textTransform: 'none' }}
                    >
                        {t('exit', 'Exit')}
                    </Button>
                </Box>

                <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 0.5 }}>
                    <div style={{
                        display: (analysisToggles.view3d && Board3D) ? 'none' : 'flex',
                        width: '100%', height: '100%',
                        justifyContent: 'center', alignItems: 'center'
                    }}>
                        <Board
                            gameState={gameState}
                            onMove={onMove}
                            analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
                            playerColor={humanColor}
                        />
                    </div>
                    {analysisToggles.view3d && Board3D && (
                        <Board3D
                            gameState={gameState}
                            onMove={onMove}
                            analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
                            playerColor={humanColor}
                        />
                    )}
                    {analysisToggles.view3d && !Board3D && <CircularProgress />}
                </Box>
            </Box>

            {/* Right Sidebar with Controls */}
            {controls()}
            </>)}
        </Box>
    );
};

export default GamePage;
