import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import Board from '../../components/Board';
import { useGameSession } from '../hooks/useGameSession';
import RightSidebarPanel from '../components/game/RightSidebarPanel';
import { useAuth } from '../../context/AuthContext';
import { useGameNavigation } from '../context/GameNavigationContext';
import { API } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';

const GameRoomPage = () => {
    const { sessionId } = useParams();
    const { user, token } = useAuth();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { registerActiveGame, unregisterActiveGame } = useGameNavigation();
    const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
    const [showGameEndDialog, setShowGameEndDialog] = useState(false);
    const [showResignConfirm, setShowResignConfirm] = useState(false);
    const [showCountConfirm, setShowCountConfirm] = useState(false);
    const [showCountRequestDialog, setShowCountRequestDialog] = useState(false);
    const [countRequesterName, setCountRequesterName] = useState<string>('');

    const handleGameEnd = useCallback(() => {
        setShowGameEndDialog(true);
    }, []);

    const handleCountRequest = useCallback((data: { requester_id: number; requester_name: string }) => {
        // Only show dialog if we're not the requester
        if (data.requester_id !== user?.id) {
            setCountRequesterName(data.requester_name);
            setShowCountRequestDialog(true);
        }
    }, [user?.id]);

    const handleCountRejected = useCallback(() => {
        alert(t('count_rejected_msg', 'Your counting request was rejected.'));
    }, [t]);

    const handleCountTimeout = useCallback(() => {
        setShowCountRequestDialog(false);
    }, []);

    const {
        sessionId: currentSessionId,
        setSessionId,
        gameState,
        error,
        onMove,
        onNavigate,
        handleAction,
        gameEndData
    } = useGameSession({
        token: token || undefined,
        onGameEnd: handleGameEnd,
        onCountRequest: handleCountRequest,
        onCountRejected: handleCountRejected,
        onCountTimeout: handleCountTimeout
    });

    useEffect(() => {
        if (sessionId && sessionId !== currentSessionId) {
            setSessionId(sessionId);
        }
    }, [sessionId, currentSessionId, setSessionId]);

    // Register/unregister active game for sidebar navigation protection
    useEffect(() => {
        const isBlack = gameState?.players_info.B.name === user?.username;
        const isWhite = gameState?.players_info.W.name === user?.username;
        const isPlayer = isBlack || isWhite;

        if (gameState && isPlayer && !gameState.end_result && !gameEndData) {
            registerActiveGame(async () => {
                if (sessionId && token) {
                    try {
                        await API.leaveMultiplayerGame(sessionId, token);
                    } catch (e) {
                        console.error("Failed to leave game:", e);
                    }
                }
            });
        } else {
            unregisterActiveGame();
        }
        return () => unregisterActiveGame();
    }, [gameState?.end_result, gameState?.players_info, gameEndData, user?.username, sessionId, token, registerActiveGame, unregisterActiveGame]);

    const handleLeaveGame = useCallback(async () => {
        if (!sessionId || !token) return;
        try {
            await API.leaveMultiplayerGame(sessionId, token);
        } catch (e) {
            console.error("Failed to leave game:", e);
        }
        navigate('/galaxy/play/human');
    }, [sessionId, token, navigate]);

    const handleBackToLobby = useCallback(() => {
        navigate('/galaxy/play/human');
    }, [navigate]);

    const handleActionWrapper = useCallback((action: string) => {
        if (action === 'resign') {
             setShowResignConfirm(true);
        } else if (action === 'count') {
             if (!gameState?.end_result) {
                 setShowCountConfirm(true);
             }
        } else {
             handleAction(action);
        }
    }, [handleAction, gameState?.end_result]);

    const confirmCount = useCallback(async () => {
        setShowCountConfirm(false);
        if (!sessionId || !token) return;
        try {
            const response = await API.requestCount(sessionId, token);
            if (response.result) {
                // Count completed immediately (e.g., other player already requested)
                setShowGameEndDialog(true);
            }
            // If status is 'pending', wait for response via WebSocket
        } catch (e: any) {
            console.error("Count request failed:", e);
            alert(e.message || "Count request failed");
        }
    }, [sessionId, token]);

    const respondToCountRequest = useCallback(async (accept: boolean) => {
        setShowCountRequestDialog(false);
        if (!sessionId || !token) return;
        try {
            await API.respondCount(sessionId, accept, token);
        } catch (e: any) {
            console.error("Count response failed:", e);
        }
    }, [sessionId, token]);

    const confirmResign = useCallback(async () => {
        setShowResignConfirm(false);
        await handleAction('resign');
    }, [handleAction]);

    if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert><Button onClick={() => navigate('/galaxy/play/human')}>Back to Lobby</Button></Box>;
    if (!gameState) return <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>;

    const isBlack = gameState.players_info.B.name === user?.username;
    const isWhite = gameState.players_info.W.name === user?.username;
    const isPlayer = isBlack || isWhite;
    const myTurn = (gameState.player_to_move === 'B' && isBlack) || (gameState.player_to_move === 'W' && isWhite);

    const spectatorCount = gameState.sockets_count !== undefined ? Math.max(0, gameState.sockets_count - 2) : 0;

    const formatResult = (result: string) => {
        const match = result.match(/^([BW])\+(.+)$/);
        if (!match) return result;
        const [, color, score] = match;
        const winner = color === 'B' ? t('result:black_win', 'B+') : t('result:white_win', 'W+');
        return `${winner}${score}${t('result:points', '')}`;
    };

    // Determine game end result message
    const getGameEndMessage = () => {
        if (!gameEndData) return "";
        const { reason, winner_id, result } = gameEndData;
        const isWinner = winner_id === user?.id;

        if (reason === 'forfeit') {
            return isWinner ? t('game_end:forfeit_win', "Your opponent left the game. You win!") : t('game_end:forfeit_loss', "You forfeited the game.");
        } else if (reason === 'resign') {
            return isWinner ? t('game_end:resign_win', "Your opponent resigned. You win!") : t('game_end:resign_loss', "You resigned.");
        } else if (reason === 'timeout') {
            return isWinner ? t('game_end:timeout_win', "Your opponent ran out of time. You win!") : t('game_end:timeout_loss', "You ran out of time.");
        } else if (reason === 'count') {
            return t('game_end:count', 'Game ended by counting: {result}').replace('{result}', formatResult(result || ''));
        } else {
            return t(result || "Game ended", result || "Game ended");
        }
    };

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            {/* Leave Confirmation Dialog */}
            <Dialog open={showLeaveConfirm} onClose={() => setShowLeaveConfirm(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('leave_game_title', 'Leave Game?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('game_room:forfeit_warning', 'Leaving the game will count as a forfeit. Your opponent will win this game. Are you sure you want to leave?')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowLeaveConfirm(false)}>{t('cancel', 'Cancel')}</Button>
                    <Button onClick={handleLeaveGame} color="error" variant="contained">{t('game_room:leave_forfeit', 'Leave & Forfeit')}</Button>
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

            {/* Game End Dialog */}
            <Dialog open={showGameEndDialog} onClose={handleBackToLobby} maxWidth="xs" fullWidth>
                <DialogTitle>{t('Game Over', 'Game Over')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {getGameEndMessage()}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleBackToLobby} variant="contained" color="primary">{t('game_room:back_to_lobby', 'Back to Lobby')}</Button>
                </DialogActions>
            </Dialog>

            {/* Count Confirmation Dialog - for initiator */}
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

            {/* Count Request Dialog - for responder */}
            <Dialog open={showCountRequestDialog} onClose={() => setShowCountRequestDialog(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('count_request_title', 'Counting Request')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('count_request_text', '{name} wants to end the game by counting. Do you agree?').replace('{name}', countRequesterName)}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => respondToCountRequest(false)} color="error">{t('reject', 'Reject')}</Button>
                    <Button onClick={() => respondToCountRequest(true)} color="primary" variant="contained">{t('accept', 'Accept')}</Button>
                </DialogActions>
            </Dialog>

            {/* Main Area: Board only */}
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.3)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 3 }}>
                    <Typography variant="subtitle2" color={myTurn ? "primary.main" : "text.secondary"}>
                        {isPlayer ? (myTurn ? t('game_room:your_turn', "Your Turn") : t('game_room:opponents_turn', "Opponent's Turn")) : t('game_room:spectating', "Spectating")}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <VisibilityIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                            <Typography variant="caption" color="text.secondary">{spectatorCount} {t('Spectators', 'Spectators')}</Typography>
                        </Box>
                        {!isPlayer && (
                            <Button
                                size="small"
                                color="inherit"
                                variant="outlined"
                                startIcon={<ExitToAppIcon />}
                                onClick={() => navigate('/galaxy/play/human')}
                                sx={{ textTransform: 'none', borderColor: 'rgba(255,255,255,0.3)', color: 'text.secondary' }}
                            >
                                {t('exit', 'Exit')}
                            </Button>
                        )}
                        {isPlayer && !gameEndData && (
                            <Button
                                size="small"
                                color="error"
                                variant="outlined"
                                startIcon={<ExitToAppIcon />}
                                onClick={() => setShowLeaveConfirm(true)}
                                sx={{ textTransform: 'none' }}
                            >
                                {t('game_room:leave', 'Leave')}
                            </Button>
                        )}
                    </Box>
                </Box>
                <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 2 }}>
                    <Board 
                        gameState={gameState} 
                        onMove={(x, y) => isPlayer ? onMove(x, y) : {}} 
                        onNavigate={onNavigate}
                        analysisToggles={{ coords: true, numbers: false }} // Fixed for HvH
                    />
                </Box>
            </Box>

            {/* Right Sidebar with Controls */}
            <RightSidebarPanel 
                gameState={gameState}
                analysisToggles={{ ownership: false, hints: false, score: false, policy: false, coords: true, numbers: false }}
                onToggleChange={() => {}} // Disabled for HvH
                onNavigate={onNavigate}
                onAction={isPlayer ? handleActionWrapper : () => {}} // Only players can act? Spectators can navigate history?
                isRated={true} // HvH usually rated
            />
        </Box>
    );
};

export default GameRoomPage;