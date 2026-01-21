import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import Board from '../../components/Board';
import { useGameSession } from '../hooks/useGameSession';
import RightSidebarPanel from '../components/game/RightSidebarPanel';
import { useAuth } from '../context/AuthContext';
import { API } from '../../api';

const GameRoomPage = () => {
    const { sessionId } = useParams();
    const { user, token } = useAuth();
    const navigate = useNavigate();
    const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
    const [showGameEndDialog, setShowGameEndDialog] = useState(false);
    const [showResignConfirm, setShowResignConfirm] = useState(false);

    const handleGameEnd = useCallback(() => {
        setShowGameEndDialog(true);
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
    } = useGameSession({ token: token || undefined, onGameEnd: handleGameEnd });

    useEffect(() => {
        if (sessionId && sessionId !== currentSessionId) {
            setSessionId(sessionId);
        }
    }, [sessionId, currentSessionId, setSessionId]);

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
        } else {
             handleAction(action);
        }
    }, [handleAction]);

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

    // Determine game end result message
    const getGameEndMessage = () => {
        if (!gameEndData) return "";
        const { reason, winner_id, result } = gameEndData;
        const isWinner = winner_id === user?.id;

        if (reason === 'forfeit') {
            return isWinner ? "Your opponent left the game. You win!" : "You forfeited the game.";
        } else if (reason === 'resign') {
            return isWinner ? "Your opponent resigned. You win!" : "You resigned.";
        } else if (reason === 'timeout') {
            return isWinner ? "Your opponent ran out of time. You win!" : "You ran out of time.";
        } else {
            return result || "Game ended";
        }
    };

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            {/* Leave Confirmation Dialog */}
            <Dialog open={showLeaveConfirm} onClose={() => setShowLeaveConfirm(false)}>
                <DialogTitle>Leave Game?</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Leaving the game will count as a forfeit. Your opponent will win this game. Are you sure you want to leave?
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowLeaveConfirm(false)}>Cancel</Button>
                    <Button onClick={handleLeaveGame} color="error" variant="contained">Leave & Forfeit</Button>
                </DialogActions>
            </Dialog>

            {/* Resign Confirmation Dialog */}
            <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
                <DialogTitle>Resign Game?</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        Are you sure you want to resign?
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowResignConfirm(false)}>Cancel</Button>
                    <Button onClick={confirmResign} color="error" variant="contained">Resign</Button>
                </DialogActions>
            </Dialog>

            {/* Game End Dialog */}
            <Dialog open={showGameEndDialog} onClose={handleBackToLobby}>
                <DialogTitle>Game Over</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {getGameEndMessage()}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleBackToLobby} variant="contained" color="primary">Back to Lobby</Button>
                </DialogActions>
            </Dialog>

            {/* Main Area: Board only */}
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.3)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 3 }}>
                    <Typography variant="subtitle2" color={myTurn ? "primary.main" : "text.secondary"}>
                        {isPlayer ? (myTurn ? "Your Turn" : "Opponent's Turn") : "Spectating"}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <VisibilityIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                            <Typography variant="caption" color="text.secondary">{spectatorCount} Spectators</Typography>
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
                                Exit
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
                                Leave
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