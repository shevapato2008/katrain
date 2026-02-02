import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, Button, LinearProgress } from '@mui/material';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import ScienceIcon from '@mui/icons-material/Science';
import LiveBoard from '../components/live/LiveBoard';
import Board from '../../components/Board';
import ResearchSetupPanel from '../components/research/ResearchSetupPanel';
import ResearchAnalysisPanel from '../components/research/ResearchAnalysisPanel';
import { useResearchBoard } from '../hooks/useResearchBoard';
import { useResearchSession } from '../hooks/useResearchSession';
import { API } from '../../api';
import { KifuAPI } from '../api/kifuApi';
import { UserGamesAPI } from '../api/userGamesApi';
import GameLibraryModal from '../components/research/CloudSGFPanel';
import { useAuth } from '../context/AuthContext';
import type { ResearchBoardState } from '../hooks/useResearchBoard';

const ResearchPage = () => {
    const [searchParams] = useSearchParams();
    const { token } = useAuth();

    // L1 ↔ L2 state
    const [isAnalyzing, setIsAnalyzing] = useState(false);

    // Game library modal
    const [libraryOpen, setLibraryOpen] = useState(false);

    // Analysis progress tracking
    const [analysisProgress, setAnalysisProgress] = useState<{ analyzed: number; total: number } | null>(null);
    const analysisComplete = analysisProgress !== null && analysisProgress.total > 0 && analysisProgress.analyzed >= analysisProgress.total;

    // Frozen snapshot for L2 → L1 restore
    const frozenSnapshot = useRef<ResearchBoardState | null>(null);

    // Cloud game ID for analysis persistence (set after saving to cloud)
    const savedGameIdRef = useRef<string | null>(null);

    // Session ID ref for polling (avoids stale closure issues)
    const activeSessionIdRef = useRef<string | null>(null);

    // ETA tracking: record first meaningful progress to compute rate
    const analysisStartRef = useRef<{ time: number; analyzed: number } | null>(null);
    const [etaSeconds, setEtaSeconds] = useState<number | null>(null);

    // Board state hook (L1)
    const board = useResearchBoard();

    // Research session hook (L2)
    const session = useResearchSession();

    // Analysis toggles for Legacy Board (L2)
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

    // beforeunload: cleanup session when user closes tab/navigates away
    useEffect(() => {
        const cleanup = () => {
            if (session.sessionId) {
                // Use fetch with keepalive for reliable cleanup on page unload
                fetch(`/api/session/${session.sessionId}`, { method: 'DELETE', keepalive: true }).catch(() => {});
            }
        };
        window.addEventListener('beforeunload', cleanup);
        return () => window.removeEventListener('beforeunload', cleanup);
    }, [session.sessionId]);

    // Deep linking: load kifu from ?kifu_id=xxx query param
    const kifuLoadedRef = useRef(false);
    useEffect(() => {
        const kifuId = searchParams.get('kifu_id');
        if (!kifuId || kifuLoadedRef.current) return;
        kifuLoadedRef.current = true;

        KifuAPI.getAlbum(Number(kifuId))
            .then((album) => {
                if (album.sgf_content) {
                    board.loadFromSGF(album.sgf_content);
                }
                if (album.player_black) board.setPlayerBlack(album.player_black);
                if (album.player_white) board.setPlayerWhite(album.player_white);

                // Auto-start analysis if ?analyze=1 is set
                if (searchParams.get('analyze') === '1') {
                    setTimeout(() => handleStartAnalysis(), 100);
                }
            })
            .catch((err) => {
                console.error('Failed to load kifu for deep link:', err);
            });
    }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

    // Poll analysis progress while analyzing and not yet complete
    useEffect(() => {
        if (!isAnalyzing || analysisComplete) return;
        const sid = activeSessionIdRef.current;
        if (!sid) return;

        const interval = setInterval(async () => {
            try {
                const progress = await API.analysisProgress(sid);
                // Only update if this session is still active
                if (activeSessionIdRef.current === sid) {
                    setAnalysisProgress({ analyzed: progress.analyzed, total: progress.total });

                    // ETA calculation
                    const now = Date.now();
                    if (progress.analyzed > 0 && progress.total > 0) {
                        if (!analysisStartRef.current || analysisStartRef.current.analyzed === 0) {
                            // Record first meaningful progress point
                            analysisStartRef.current = { time: now, analyzed: progress.analyzed };
                        } else {
                            const elapsed = (now - analysisStartRef.current.time) / 1000; // seconds
                            const done = progress.analyzed - analysisStartRef.current.analyzed;
                            if (done > 0 && elapsed > 2) {
                                const rate = done / elapsed; // moves per second
                                const remaining = progress.total - progress.analyzed;
                                setEtaSeconds(Math.round(remaining / rate));
                            }
                        }
                    }
                }
            } catch {
                // Ignore errors during polling
            }
        }, 1000);

        return () => clearInterval(interval);
    }, [isAnalyzing, analysisComplete]);

    // When analysis completes, navigate to the last move to get full state
    useEffect(() => {
        if (analysisComplete && session.gameState) {
            const gs = session.gameState;
            const currentNodeId = gs.history[gs.current_node_index]?.node_id;
            if (currentNodeId !== undefined) {
                session.onNavigate(currentNodeId);
            }
        }
    }, [analysisComplete]); // eslint-disable-line react-hooks/exhaustive-deps

    // Auto-save analysis to cloud when complete (if logged in)
    useEffect(() => {
        if (!analysisComplete || !token || !activeSessionIdRef.current) return;
        const sessionId = activeSessionIdRef.current;
        (async () => {
            try {
                // Save the game first if not already saved
                if (!savedGameIdRef.current) {
                    const { sgf } = board.serializeToSGF();
                    const created = await UserGamesAPI.create(token, {
                        sgf_content: sgf,
                        source: 'research',
                        title: board.playerBlack && board.playerWhite
                            ? `${board.playerBlack} vs ${board.playerWhite}`
                            : undefined,
                        player_black: board.playerBlack || undefined,
                        player_white: board.playerWhite || undefined,
                        board_size: board.boardSize,
                        rules: board.rules,
                        komi: board.komi,
                        move_count: board.moves.length,
                        category: 'game',
                    });
                    savedGameIdRef.current = created.id;
                }
                // Save analysis data from the session
                await UserGamesAPI.saveAnalysisFromSession(token, savedGameIdRef.current, sessionId);
            } catch (err) {
                console.error('Failed to auto-save analysis:', err);
            }
        })();
    }, [analysisComplete]); // eslint-disable-line react-hooks/exhaustive-deps

    // Derive winrate/scoreLead from gameState analysis root
    const analysisData = useMemo(() => {
        const gs = session.gameState;
        if (!gs?.analysis) return { winrate: 0.5, scoreLead: 0 };
        return {
            winrate: gs.analysis.winrate ?? 0.5,
            scoreLead: gs.analysis.score ?? 0,
        };
    }, [session.gameState]);

    // Cloud save: save current board state to user_games
    const handleSaveToCloud = useCallback(async () => {
        if (!token) return;
        const { sgf } = board.serializeToSGF();
        try {
            await UserGamesAPI.create(token, {
                sgf_content: sgf,
                source: 'research',
                title: board.playerBlack && board.playerWhite
                    ? `${board.playerBlack} vs ${board.playerWhite}`
                    : undefined,
                player_black: board.playerBlack || undefined,
                player_white: board.playerWhite || undefined,
                board_size: board.boardSize,
                rules: board.rules,
                komi: board.komi,
                move_count: board.moves.length,
                category: 'game',
            });
        } catch (err) {
            console.error('Failed to save to cloud:', err);
        }
    }, [token, board]);

    // Cloud load: open game library modal
    const handleOpenFromCloud = useCallback(() => {
        setLibraryOpen(true);
    }, []);

    // Load game from library modal
    const handleLoadFromLibrary = useCallback((sgf: string) => {
        board.loadFromSGF(sgf);
    }, [board]);

    // Start analysis (L1 → L2)
    const handleStartAnalysis = useCallback(async () => {
        // 1. Freeze L1 snapshot
        frozenSnapshot.current = board.getSnapshot();

        // 2. Serialize to SGF
        const { sgf } = board.serializeToSGF();

        // 3. Create research session and load SGF (skip bulk analysis to avoid timeouts)
        const sgfToLoad = board.moves.length > 0 ? sgf : undefined;
        const newSessionId = await session.createSession(sgfToLoad, {
            skipAnalysis: true,
            initialMove: board.currentMove,
        });

        if (newSessionId) {
            // 4. Switch to L2
            activeSessionIdRef.current = newSessionId;
            setAnalysisProgress(null);
            setEtaSeconds(null);
            analysisStartRef.current = null;
            setIsAnalyzing(true);
            // 5. Trigger full analysis scan (500 visits per node, engine queues internally)
            API.analysisScan(newSessionId, 500);
        }
    }, [board, session]);

    // Return to edit (L2 → L1)
    const handleReturnToEdit = useCallback(async () => {
        // 1. Cleanup session
        activeSessionIdRef.current = null;
        savedGameIdRef.current = null;
        await session.destroySession();

        // 2. Restore frozen snapshot
        if (frozenSnapshot.current) {
            board.restoreSnapshot(frozenSnapshot.current);
            frozenSnapshot.current = null;
        }

        // 3. Switch to L1
        setIsAnalyzing(false);
        setAnalysisProgress(null);
        setEtaSeconds(null);
        analysisStartRef.current = null;
        setAnalysisToggles(prev => ({ ...prev, hints: false, ownership: false, policy: false }));
    }, [session, board]);

    // L2 navigation - use node_id from history for direct jumps
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

    // ──────────────────────────── L2: Analysis Mode (complete) ────────────────────────────
    if (isAnalyzing && analysisComplete && session.gameState) {
        const gs = session.gameState;
        const totalMoves = gs.history.length - 1; // exclude root
        const currentMove = gs.current_node_index;

        return (
            <>
                <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
                    {/* Main Board Area */}
                    <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                        {/* Header */}
                        <Box sx={{
                            p: 1,
                            bgcolor: 'rgba(0,0,0,0.3)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            px: 3,
                        }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                <ScienceIcon sx={{ fontSize: 18, color: 'primary.main' }} />
                                <Typography variant="subtitle2" color="primary.main">
                                    研究模式
                                </Typography>
                            </Box>
                            <Button
                                size="small"
                                color="error"
                                variant="outlined"
                                startIcon={<ExitToAppIcon />}
                                onClick={handleReturnToEdit}
                                sx={{ textTransform: 'none' }}
                            >
                                返回编辑
                            </Button>
                        </Box>

                        {/* Board - Legacy Board with GameState */}
                        <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center', p: 0.5 }}>
                            <Board
                                gameState={gs}
                                onMove={session.onMove}
                                analysisToggles={analysisToggles}
                            />
                        </Box>
                    </Box>

                    {/* Right Sidebar: Analysis Panel */}
                    <ResearchAnalysisPanel
                        playerBlack={gs.players_info?.B?.name || board.playerBlack || '黑方'}
                        playerWhite={gs.players_info?.W?.name || board.playerWhite || '白方'}
                        currentMove={currentMove}
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
                        onSaveToCloud={handleSaveToCloud}
                        onOpenFromCloud={handleOpenFromCloud}
                        analysisMoves={gs.analysis?.moves}
                        history={gs.history}
                        playerToMove={gs.player_to_move}
                    />
                </Box>
                <GameLibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} onLoadGame={handleLoadFromLibrary} />
            </>
        );
    }

    // ──────────────────────────── L2: Analysis in Progress ────────────────────────────
    if (isAnalyzing) {
        const progressPercent = analysisProgress && analysisProgress.total > 0
            ? Math.round((analysisProgress.analyzed / analysisProgress.total) * 100)
            : 0;

        return (
            <Box sx={{ display: 'flex', height: '100vh', justifyContent: 'center', alignItems: 'center', bgcolor: '#0f0f0f' }}>
                <Box sx={{ textAlign: 'center', width: 400 }}>
                    <ScienceIcon sx={{ fontSize: 48, color: 'primary.main', mb: 2 }} />
                    <Typography variant="h6" color="text.primary" sx={{ mb: 1 }}>
                        正在分析棋局
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        {analysisProgress
                            ? `已完成 ${analysisProgress.analyzed} / ${analysisProgress.total} 步`
                            : '正在连接研究会话...'
                        }
                    </Typography>

                    {/* Progress bar */}
                    <Box sx={{ mx: 2, mb: 1 }}>
                        <LinearProgress
                            variant={analysisProgress ? 'determinate' : 'indeterminate'}
                            value={progressPercent}
                            sx={{
                                height: 10,
                                borderRadius: 5,
                                bgcolor: 'rgba(255,255,255,0.1)',
                                '& .MuiLinearProgress-bar': {
                                    borderRadius: 5,
                                    bgcolor: 'primary.main',
                                },
                            }}
                        />
                    </Box>
                    {analysisProgress && (
                        <Box sx={{ mb: 3 }}>
                            <Typography variant="body2" color="primary.main" sx={{ fontWeight: 700, fontFamily: '"IBM Plex Mono", monospace' }}>
                                {progressPercent}%
                            </Typography>
                            {etaSeconds !== null && etaSeconds > 0 && (
                                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontFamily: '"IBM Plex Mono", monospace' }}>
                                    预计剩余 {etaSeconds >= 60 ? `${Math.floor(etaSeconds / 60)}分${(etaSeconds % 60).toString().padStart(2, '0')}秒` : `${etaSeconds}秒`}
                                </Typography>
                            )}
                        </Box>
                    )}

                    <Button
                        size="small"
                        color="error"
                        variant="text"
                        onClick={handleReturnToEdit}
                        sx={{ mt: 1, textTransform: 'none' }}
                    >
                        取消
                    </Button>
                </Box>
            </Box>
        );
    }

    // ──────────────────────────── L1: Setup / Edit Mode ────────────────────────────
    return (
        <>
            <Box sx={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
                {/* Main Board Area */}
                <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column', bgcolor: '#0f0f0f' }}>
                    {/* Board */}
                    <Box sx={{ flexGrow: 1, display: 'flex', justifyContent: 'center', alignItems: 'center' }}>
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
                        />
                    </Box>

                    {/* Bottom Navigation */}
                    <Box sx={{
                        px: 3,
                        py: 1.5,
                        bgcolor: '#1a1a1a',
                        borderTop: '1px solid rgba(255,255,255,0.05)',
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        gap: 1,
                    }}>
                        <Button
                            size="small"
                            disabled={board.currentMove === 0}
                            onClick={() => board.handleMoveChange(0)}
                            sx={{ minWidth: 32, color: 'text.secondary' }}
                        >
                            ⏮
                        </Button>
                        <Button
                            size="small"
                            disabled={board.currentMove === 0}
                            onClick={() => board.handleMoveChange(board.currentMove - 1)}
                            sx={{ minWidth: 32, color: 'text.secondary' }}
                        >
                            ◀
                        </Button>
                        <Typography
                            variant="body2"
                            sx={{
                                mx: 2,
                                fontFamily: '"IBM Plex Mono", monospace',
                                color: 'text.secondary',
                                minWidth: 80,
                                textAlign: 'center',
                            }}
                        >
                            {Math.max(0, board.currentMove - board.handicapCount)} / {board.moves.length - board.handicapCount} 手
                        </Typography>
                        <Button
                            size="small"
                            disabled={board.currentMove >= board.moves.length}
                            onClick={() => board.handleMoveChange(board.currentMove + 1)}
                            sx={{ minWidth: 32, color: 'text.secondary' }}
                        >
                            ▶
                        </Button>
                        <Button
                            size="small"
                            disabled={board.currentMove >= board.moves.length}
                            onClick={() => board.handleMoveChange(board.moves.length)}
                            sx={{ minWidth: 32, color: 'text.secondary' }}
                        >
                            ⏭
                        </Button>
                    </Box>
                </Box>

                {/* Right Sidebar: Setup Panel */}
                <ResearchSetupPanel
                    playerBlack={board.playerBlack}
                    playerWhite={board.playerWhite}
                    onPlayerBlackChange={board.setPlayerBlack}
                    onPlayerWhiteChange={board.setPlayerWhite}
                    boardSize={board.boardSize}
                    onBoardSizeChange={board.setBoardSize}
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
                    onClear={board.handleClear}
                    onOpen={board.openLocalSGF}
                    onSave={board.saveLocalSGF}
                    onCopyToClipboard={board.copyToClipboard}
                    onSaveToCloud={handleSaveToCloud}
                    onOpenFromCloud={handleOpenFromCloud}
                    onStartAnalysis={handleStartAnalysis}
                />
            </Box>
            <GameLibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} onLoadGame={handleLoadFromLibrary} />
        </>
    );
};

export default ResearchPage;
