import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Typography, Button } from '@mui/material';
import VisibilityIcon from '@mui/icons-material/Visibility';
import Board from '../../components/Board';
import ControlBar from '../../components/ControlBar';
import { useGameSession } from '../hooks/useGameSession';
import RightSidebarPanel from '../components/game/RightSidebarPanel';
import { useAuth } from '../context/AuthContext';

const GameRoomPage = () => {
    const { sessionId } = useParams();
    const { user } = useAuth();
    const navigate = useNavigate();

    const { 
        sessionId: currentSessionId, 
        setSessionId, 
        gameState, 
        error, 
        onMove, 
        onNavigate,
        handleAction 
    } = useGameSession();

    useEffect(() => {
        if (sessionId && sessionId !== currentSessionId) {
            setSessionId(sessionId);
        }
    }, [sessionId, currentSessionId, setSessionId]);

    if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert><Button onClick={() => navigate('/galaxy/play/human')}>Back to Lobby</Button></Box>;
    if (!gameState) return <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>;

    const isBlack = gameState.players_info.B.name === user?.username;
    const isWhite = gameState.players_info.W.name === user?.username;
    const isPlayer = isBlack || isWhite;
    const myTurn = (gameState.player_to_move === 'B' && isBlack) || (gameState.player_to_move === 'W' && isWhite);

    const spectatorCount = gameState.sockets_count !== undefined ? Math.max(0, gameState.sockets_count - 2) : 0;

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            {/* Main Area: Board + ControlBar */}
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.3)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 3 }}>
                    <Typography variant="subtitle2" color={myTurn ? "primary.main" : "text.secondary"}>
                        {isPlayer ? (myTurn ? "Your Turn" : "Opponent's Turn") : "Spectating"}
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <VisibilityIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                        <Typography variant="caption" color="text.secondary">{spectatorCount} Spectators</Typography>
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
                
                {/* Control Bar */}
                <Box sx={{ bgcolor: 'background.paper', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                    <ControlBar 
                        onAction={handleAction} 
                        nextPlayer={gameState.player_to_move} 
                        disabled={!isPlayer}
                    />
                </Box>
            </Box>

            {/* Right Sidebar */}
            <RightSidebarPanel 
                gameState={gameState}
                analysisToggles={{ ownership: false, hints: false, score: false, policy: false, coords: true, numbers: false }}
                onToggleChange={() => {}} // Disabled for HvH
                onNavigate={onNavigate}
                isRated={true} // HvH usually rated
            />
        </Box>
    );
};

export default GameRoomPage;
