import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Box, Typography, Button, LinearProgress } from '@mui/material';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import ScienceIcon from '@mui/icons-material/Science';
import LiveBoard, { type AiMoveMarker } from '../components/live/LiveBoard';
import Board from '../../components/Board';
import ResearchSetupPanel from '../components/research/ResearchSetupPanel';
import ResearchAnalysisPanel from '../components/research/ResearchAnalysisPanel';
import { useResearchBoard } from '../hooks/useResearchBoard';
import { useResearchSession } from '../hooks/useResearchSession';
import { useTranslation } from '../../hooks/useTranslation';
import { API } from '../../api';
import { KifuAPI } from '../api/kifuApi';
import { UserGamesAPI } from '../api/userGamesApi';
import GameLibraryModal from '../components/research/CloudSGFPanel';
import { useAuth } from '../../context/AuthContext';
import { useGameNavigation } from '../context/GameNavigationContext';
import type { ResearchBoardState } from '../hooks/useResearchBoard';

const ResearchPage = () => {
    const [searchParams] = useSearchParams();
    const { token } = useAuth();
    const { t } = useTranslation();
    const { registerActiveGame, unregisterActiveGame } = useGameNavigation();

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

    // Guard: enable hints only once per analysis session
    const hintsEnabledRef = useRef(false);
    const [etaSeconds, setEtaSeconds] = useState<number | null>(null);

    // Board state hook (L1)
    const board = useResearchBoard();

    // Stone placement sound for L1
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const prevMoveRef = useRef<number>(0);
    useEffect(() => {
        // Play sound when currentMove changes (stone placed or navigation)
        if (board.currentMove !== prevMoveRef.current) {
            prevMoveRef.current = board.currentMove;
            if (!isAnalyzing) {
                if (!audioRef.current) {
                    audioRef.current = new Audio('/assets/sounds/stone1.wav');
                }
                const audio = audioRef.current;
                audio.currentTime = 0;
                audio.play().catch(() => {});
            }
        }
    }, [board.currentMove, isAnalyzing]);

    // L1 quick analysis: hints + territory
    const [l1ShowHints, setL1ShowHints] = useState(false);
    const [l1ShowTerritory, setL1ShowTerritory] = useState(false);
    const [l1AiMarkers, setL1AiMarkers] = useState<AiMoveMarker[] | null>(null);
    const [l1Ownership, setL1Ownership] = useState<number[][] | null>(null);
    const [l1AnalysisPending, setL1AnalysisPending] = useState(false);
    const l1AnalysisKeyRef = useRef<string>('');

    // Build a key representing the current board position for cache invalidation
    const l1PositionKey = useMemo(() => {
        return `${board.boardSize}-${board.komi}-${board.rules}-${board.currentMove}-${board.moves.slice(0, board.currentMove).join(',')}`;
    }, [board.boardSize, board.komi, board.rules, board.currentMove, board.moves]);

    // Fetch quick analysis when hints or territory is toggled on, or position changes while active
    useEffect(() => {
        if (isAnalyzing) return; // L2 handles its own analysis
        if (!l1ShowHints && !l1ShowTerritory) {
            // Clear stale data when both off
            setL1AiMarkers(null);
            setL1Ownership(null);
            return;
        }
        const key = l1PositionKey;
        l1AnalysisKeyRef.current = key;
        setL1AnalysisPending(true);

        // Convert board moves to KataGo format [["B","Q16"],["W","D4"],...]
        const movesUpToCurrent = board.moves.slice(0, board.currentMove);
        const colors = board.stoneColors.slice(0, board.currentMove);
        const kataMoves = movesUpToCurrent.map((m, i) => [colors[i], m]);

        API.quickAnalyze({
            moves: kataMoves,
            board_size: board.boardSize,
            komi: board.komi,
            rules: board.rules,
            max_visits: 200,
        }).then((result) => {
            if (l1AnalysisKeyRef.current !== key) return; // stale
            // Parse top moves for hints
            const turnResult = result?.turnInfos?.[0] ?? result;
            const moveInfos = turnResult?.moveInfos ?? [];
            const markers: AiMoveMarker[] = moveInfos.slice(0, 5).map((mi: any, idx: number) => ({
                move: mi.move,
                rank: idx + 1,
                visits: mi.visits,
                winrate: mi.winrate,
                score_lead: mi.scoreLead ?? 0,
            }));
            setL1AiMarkers(markers);

            // Parse ownership grid
            const rawOwnership = turnResult?.ownership;
            if (rawOwnership && Array.isArray(rawOwnership)) {
                // KataGo returns flat array of length boardSize*boardSize
                const size = board.boardSize;
                const grid: number[][] = [];
                for (let y = 0; y < size; y++) {
                    grid.push(rawOwnership.slice(y * size, (y + 1) * size));
                }
                setL1Ownership(grid);
            }
        }).catch((err) => {
            console.error('Quick analysis failed:', err);
        }).finally(() => {
            if (l1AnalysisKeyRef.current === key) setL1AnalysisPending(false);
        });
    }, [l1ShowHints, l1ShowTerritory, l1PositionKey, isAnalyzing]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleL1ToggleHints = useCallback(() => setL1ShowHints(prev => !prev), []);
    const handleL1ToggleTerritory = useCallback(() => setL1ShowTerritory(prev => !prev), []);

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

    // When analysis completes, navigate to the last move to get full state and enable hints
    useEffect(() => {
        if (analysisComplete && session.gameState && !hintsEnabledRef.current) {
            hintsEnabledRef.current = true;
            const gs = session.gameState;
            const currentNodeId = gs.history[gs.current_node_index]?.node_id;
            if (currentNodeId !== undefined) {
                session.onNavigate(currentNodeId);
            }
            // Enable hints (Advice button) by default when analysis completes
            setAnalysisToggles(prev => ({ ...prev, hints: true }));
            session.toggleHints();
        }
    }, [analysisComplete, session.gameState]); // eslint-disable-line react-hooks/exhaustive-deps

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
            hintsEnabledRef.current = false;
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
        hintsEnabledRef.current = false;
        setAnalysisToggles(prev => ({ ...prev, hints: false, ownership: false, policy: false }));
    }, [session, board]);

    // Register navigation guard when analysis is in progress
    useEffect(() => {
        if (isAnalyzing) {
            registerActiveGame(handleReturnToEdit, {
                title: t('research:cancel_analysis_title', '取消分析？'),
                message: t('research:cancel_analysis_warning', '分析正在进行中，确定要取消吗？'),
                cancelLabel: t('research:continue_analysis', '继续分析'),
                confirmLabel: t('research:cancel_and_leave', '取消并离开'),
            });
        } else {
            unregisterActiveGame();
        }
    }, [isAnalyzing]); // eslint-disable-line react-hooks/exhaustive-deps

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
                                    {t('research:mode', '研究模式')}
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
                                {t('research:return_to_edit', '返回编辑')}
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
                        playerBlack={gs.players_info?.B?.name || board.playerBlack || t('research:black', '黑方')}
                        playerWhite={gs.players_info?.W?.name || board.playerWhite || t('research:white', '白方')}
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
                        children={gs.children}
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
                        {t('research:analyzing_game', '正在分析棋局')}
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
                        {analysisProgress
                            ? t('research:progress', '已完成 {analyzed} / {total} 步').replace('{analyzed}', String(analysisProgress.analyzed)).replace('{total}', String(analysisProgress.total))
                            : t('research:connecting', '正在连接研究会话...')
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
                                    {t('research:eta', '预计剩余 {time}').replace('{time}',
                                        etaSeconds >= 60
                                            ? t('research:time_min_sec', '{min}分{sec}秒').replace('{min}', String(Math.floor(etaSeconds / 60))).replace('{sec}', (etaSeconds % 60).toString().padStart(2, '0'))
                                            : t('research:time_sec', '{sec}秒').replace('{sec}', String(etaSeconds))
                                    )}
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
                        {t('research:cancel', '取消')}
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
                            aiMarkers={l1ShowHints ? l1AiMarkers : null}
                            showAiMarkers={l1ShowHints}
                            showTerritory={l1ShowTerritory}
                            ownership={l1Ownership}
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
                            {t('research:move_counter', '{current} / {total} 手').replace('{current}', String(Math.max(0, board.currentMove - board.handicapCount))).replace('{total}', String(board.moves.length - board.handicapCount))}
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
                    showHints={l1ShowHints}
                    onToggleHints={handleL1ToggleHints}
                    showTerritory={l1ShowTerritory}
                    onToggleTerritory={handleL1ToggleTerritory}
                    isAnalysisPending={l1AnalysisPending}
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
