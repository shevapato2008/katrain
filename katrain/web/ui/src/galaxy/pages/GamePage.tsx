import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@mui/material';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import Board from '../../components/Board';
import { useGameSession } from '../hooks/useGameSession';
import RightSidebarPanel from '../components/game/RightSidebarPanel';
import { useSettings } from '../../context/SettingsContext';
import { useGameNavigation } from '../context/GameNavigationContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API } from '../../api';
import { useAuth } from '../../context/AuthContext';

const GamePage = () => {
    const { sessionId } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    useSettings(); // Subscribe to translation changes for re-render
    const { t } = useTranslation();
    const { token } = useAuth();
    const { registerActiveGame, unregisterActiveGame } = useGameNavigation();
    const mode = searchParams.get('mode') || 'free';
    const isRated = mode === 'rated';

    const {
        sessionId: currentSessionId,
        setSessionId,
        gameState,
        setGameState,
        error,
        onMove,
        onNavigate,
        handleAction
    } = useGameSession();

    // Analysis Toggles State
    const [analysisToggles, setAnalysisToggles] = useState<Record<string, boolean>>({
        children: false,
        eval: false,
        hints: false,
        policy: false,
        ownership: false,
        coords: true,
        numbers: false,
        score: true,
        winrate: true
    });

    // Track move count for resetting hints after user move (Case 3)
    const prevMoveCountRef = useRef<number>(0);
    // Track if we're waiting for analysis to auto-show (Case 2)
    const waitingForAnalysisRef = useRef<boolean>(false);

    const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
    const [showResignConfirm, setShowResignConfirm] = useState(false);
    const [showCountConfirm, setShowCountConfirm] = useState(false);
    const [countResult, setCountResult] = useState<string | null>(null);
    const audioCache = useRef<Record<string, HTMLAudioElement>>({});

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
        if (!gameState?.end_result) {
            console.log('Timer expired - triggering timeout');
            await handleAction('timeout');
        }
    }, [gameState?.end_result, handleAction]);

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
        if (gameState && !gameState.end_result) {
            registerActiveGame(async () => {
                await handleAction('resign');
            });
        } else {
            unregisterActiveGame();
        }
        return () => unregisterActiveGame();
    }, [gameState?.end_result, registerActiveGame, unregisterActiveGame, handleAction]);

    const handleToggleChange = (setting: string) => {
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
        if (action === 'resign') {
            if (!gameState?.end_result) {
                setShowResignConfirm(true);
            }
        } else if (action === 'count') {
            if (!gameState?.end_result) {
                setShowCountConfirm(true);
            }
        } else {
            handleAction(action);
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
        setShowResignConfirm(false);
        await handleAction('resign');
    };

    const handleLeaveRequest = () => {
        if (!gameState?.end_result) {
            setShowLeaveConfirm(true);
        } else {
            navigate('/galaxy/play/ai');
        }
    };

    const handleConfirmLeave = async () => {
        await handleAction('resign');
        navigate('/galaxy/play/ai');
    };

    const formatResult = (result: string) => {
        const match = result.match(/^([BW])\+(.+)$/);
        if (!match) return result;
        const [, color, score] = match;
        const winner = color === 'B' ? t('result:black_win', 'B+') : t('result:white_win', 'W+');
        return `${winner}${score}${t('result:points', '')}`;
    };

    // Determine which color the human player controls (if any)
    const humanColor: 'B' | 'W' | null = gameState?.players_info?.B?.player_type === 'player:human' ? 'B'
        : gameState?.players_info?.W?.player_type === 'player:human' ? 'W'
        : null;

    if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert></Box>;
    if (!gameState) return <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>;

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
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
                        {t('game_end:count', 'Game ended by counting: {result}').replace('{result}', formatResult(countResult || ''))}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setCountResult(null)} variant="contained">{t('ok', 'OK')}</Button>
                </DialogActions>
            </Dialog>

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
                    <Board
                        gameState={gameState}
                        onMove={onMove}
                        onNavigate={onNavigate}
                        analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
                        playerColor={humanColor}
                    />
                </Box>
            </Box>

            {/* Right Sidebar with Controls */}
            <RightSidebarPanel
                gameState={gameState}
                analysisToggles={analysisToggles}
                onToggleChange={handleToggleChange}
                onNavigate={onNavigate}
                onAction={handleActionWrapper}
                isRated={isRated}
                onTimeout={handleTimeout}
                onPlaySound={handlePlaySound}
                isAnalysisPending={analysisToggles.hints && !gameState.analysis?.top_moves?.length}
            />
        </Box>
    );
};

export default GamePage;