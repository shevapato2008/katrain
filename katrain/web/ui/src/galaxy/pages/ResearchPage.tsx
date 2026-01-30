import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, Tabs, Tab } from '@mui/material';
import { AuthGuard } from '../components/guards/AuthGuard';
import Board from '../../components/Board'; // Legacy
import AnalysisPanel from '../../components/AnalysisPanel'; // Legacy
import ScoreGraph from '../../components/ScoreGraph'; // Legacy
import { useGameSession } from '../hooks/useGameSession';
import CloudSGFPanel from '../components/research/CloudSGFPanel';
import { i18n } from '../../i18n';
import { KifuAPI } from '../api/kifuApi';
import { API } from '../../api';

const ResearchPage = () => {
    const { gameState, onMove, onNavigate, sessionId, initNewSession } = useGameSession();
    const [searchParams] = useSearchParams();
    const kifuId = searchParams.get('kifu_id');
    const [kifuLoaded, setKifuLoaded] = useState<string | null>(null);

    useEffect(() => {
        if (!sessionId) {
            initNewSession();
        }
    }, [sessionId, initNewSession]);

    // Load SGF from kifu album when navigating from KifuLibraryPage
    useEffect(() => {
        if (kifuId && sessionId && kifuLoaded !== kifuId) {
            KifuAPI.getAlbum(Number(kifuId)).then((album) => {
                API.loadSGF(sessionId, album.sgf_content).then(() => {
                    setKifuLoaded(kifuId);
                });
            }).catch((err) => {
                console.error('Failed to load kifu:', err);
            });
        }
    }, [kifuId, sessionId, kifuLoaded]);

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
