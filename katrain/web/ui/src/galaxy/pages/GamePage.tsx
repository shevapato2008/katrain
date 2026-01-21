import { useState, useEffect } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Typography, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@mui/material';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import Board from '../../components/Board';
import { useGameSession } from '../hooks/useGameSession';
import RightSidebarPanel from '../components/game/RightSidebarPanel';
import { useSettings } from '../context/SettingsContext';
import { i18n } from '../../i18n';

const GamePage = () => {
    const { sessionId } = useParams();
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    useSettings(); // Subscribe to translation changes for re-render
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

    const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
    const [showResignConfirm, setShowResignConfirm] = useState(false);

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
    };

    const handleActionWrapper = (action: string) => {
        if (action === 'resign') {
            if (!gameState?.end_result) {
                setShowResignConfirm(true);
            }
        } else {
            handleAction(action);
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

    if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert></Box>;
    if (!gameState) return <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>;

    return (
        <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
            {/* Leave Confirmation Dialog */}
            <Dialog open={showLeaveConfirm} onClose={() => setShowLeaveConfirm(false)}>
                <DialogTitle>{i18n.t('leave_game_title', 'Leave Game?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {i18n.t('leave_game_warning', 'The game is still in progress. Leaving will resign the game. Are you sure?')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowLeaveConfirm(false)}>{i18n.t('cancel', 'Cancel')}</Button>
                    <Button onClick={handleConfirmLeave} color="error" variant="contained">{i18n.t('resign_and_exit', 'Resign & Exit')}</Button>
                </DialogActions>
            </Dialog>

            {/* Resign Confirmation Dialog */}
            <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)}>
                <DialogTitle>{i18n.t('resign_game_title', 'Resign Game?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {i18n.t('resign_confirm_text', 'Are you sure you want to resign?')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowResignConfirm(false)}>{i18n.t('cancel', 'Cancel')}</Button>
                    <Button onClick={confirmResign} color="error" variant="contained">{i18n.t('RESIGN', 'Resign')}</Button>
                </DialogActions>
            </Dialog>

            {/* Main Area: Board only */}
            <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                {/* Header */}
                <Box sx={{ p: 1, bgcolor: 'rgba(0,0,0,0.3)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', px: 3 }}>
                    <Typography variant="subtitle2" color="primary.main">
                        {i18n.t('play_vs_ai', 'Play vs AI')} ({mode})
                    </Typography>
                    <Button
                        size="small"
                        color="error"
                        variant="outlined"
                        startIcon={<ExitToAppIcon />}
                        onClick={handleLeaveRequest}
                        sx={{ textTransform: 'none' }}
                    >
                        {i18n.t('exit', 'Exit')}
                    </Button>
                </Box>

                <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 2 }}>
                    <Board 
                        gameState={gameState} 
                        onMove={onMove} 
                        onNavigate={onNavigate}
                        analysisToggles={isRated ? { coords: analysisToggles.coords, numbers: analysisToggles.numbers } : analysisToggles}
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
            />
        </Box>
    );
};

export default GamePage;