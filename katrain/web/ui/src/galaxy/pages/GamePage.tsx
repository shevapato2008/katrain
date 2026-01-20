import { useState, useEffect } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { Box, CircularProgress, Alert } from '@mui/material';
import Board from '../../components/Board';
import ControlBar from '../../components/ControlBar';
import { useGameSession } from '../hooks/useGameSession';
import RightSidebarPanel from '../components/game/RightSidebarPanel';

const GamePage = () => {
    const { sessionId } = useParams();
    const [searchParams] = useSearchParams();
    const mode = searchParams.get('mode') || 'free';
    const isRated = mode === 'rated';

    const { 
        sessionId: currentSessionId, 
        setSessionId, 
        gameState, 
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

    useEffect(() => {
        if (sessionId && sessionId !== currentSessionId) {
            setSessionId(sessionId);
        }
    }, [sessionId, currentSessionId, setSessionId]);

    // Sync with gameState.ui_state if available
    useEffect(() => {
        if (gameState?.ui_state) {
            setAnalysisToggles(prev => ({
                ...prev,
                hints: gameState.ui_state.show_hints,
                policy: gameState.ui_state.show_policy,
                ownership: gameState.ui_state.show_ownership,
                coords: gameState.ui_state.show_coordinates,
                numbers: gameState.ui_state.show_move_numbers,
            }));
        }
    }, [gameState]);

    const handleToggleChange = (setting: string) => {
        setAnalysisToggles(prev => ({ ...prev, [setting]: !prev[setting] }));
        // Map UI toggles to KaTrain config settings if needed
        // For now, we just pass them to the Board component props
    };

    if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert></Box>;
    if (!gameState) return <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>;

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            {/* Main Area: Board + ControlBar */}
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 2 }}>
                    <Board 
                        gameState={gameState} 
                        onMove={onMove} 
                        onNavigate={onNavigate}
                        analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
                    />
                </Box>
                
                {/* Control Bar below board */}
                <Box sx={{ bgcolor: 'background.paper', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                    <ControlBar 
                        onAction={handleAction} 
                        nextPlayer={gameState.player_to_move} 
                    />
                </Box>
            </Box>

            {/* Right Sidebar */}
            <RightSidebarPanel 
                gameState={gameState}
                analysisToggles={analysisToggles}
                onToggleChange={handleToggleChange}
                onNavigate={onNavigate}
                isRated={isRated}
            />
        </Box>
    );
};

export default GamePage;
