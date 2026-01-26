import { useState, useEffect } from 'react';
import { Box, Typography, Tabs, Tab } from '@mui/material';
import { AuthGuard } from '../components/guards/AuthGuard';
import Board from '../../components/Board'; // Legacy
import AnalysisPanel from '../../components/AnalysisPanel'; // Legacy
import ScoreGraph from '../../components/ScoreGraph'; // Legacy
import { useGameSession } from '../hooks/useGameSession';
import CloudSGFPanel from '../components/research/CloudSGFPanel';
import { i18n } from '../../i18n';

const ResearchPage = () => {
    const { gameState, onMove, onNavigate, sessionId, initNewSession } = useGameSession();

    useEffect(() => {
        if (!sessionId) {
            initNewSession();
        }
    }, [sessionId, initNewSession]);
    const [tab, setTab] = useState(0);
    
    return (
        <AuthGuard>
            <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
                {/* Main Board Area */}
                <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', position: 'relative' }}>
                    <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', bgcolor: '#262626' }}>
                        {gameState ? (
                            <Board
                                gameState={gameState}
                                onMove={(x, y) => onMove(x, y)}
                                onNavigate={onNavigate}
                                analysisToggles={{ coords: true }}
                            />
                        ) : (
                            <Typography color="text.secondary">{i18n.t('Loading Board...', 'Loading Board...')}</Typography>
                        )}
                    </Box>
                    {/* Graph Area */}
                    <Box sx={{ height: 150, borderTop: '1px solid #444', bgcolor: '#1e1e1e' }}>
                         {gameState && <ScoreGraph gameState={gameState} onNavigate={onNavigate} showScore={true} showWinrate={true} />}
                    </Box>
                </Box>

                {/* Right Panel */}
                <Box sx={{ width: 350, borderLeft: '1px solid #444', bgcolor: '#1e1e1e', display: 'flex', flexDirection: 'column' }}>
                    <Tabs value={tab} onChange={(_, v) => setTab(v)} variant="fullWidth">
                        <Tab label={i18n.t('Analysis', 'Analysis')} />
                        <Tab label={i18n.t('Library', 'Library')} />
                    </Tabs>
                    
                    <Box sx={{ flexGrow: 1, overflow: 'hidden' }}>
                        {tab === 0 && gameState && (
                            <AnalysisPanel 
                                gameState={gameState}
                                onNodeAction={() => {}}
                                onShowPV={() => {}}
                                onClearPV={() => {}}
                            />
                        )}
                        {tab === 1 && (
                            <CloudSGFPanel />
                        )}
                    </Box>
                </Box>
            </Box>
        </AuthGuard>
    );
};

export default ResearchPage;
