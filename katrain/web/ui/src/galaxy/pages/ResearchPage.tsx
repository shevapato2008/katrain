import { useState, useCallback, useRef, useMemo, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Alert, Box, Typography, Button, LinearProgress } from '@mui/material';
import ExitToAppIcon from '@mui/icons-material/ExitToApp';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import Board from '../../components/Board';
import ResearchSetupPanel, { ResearchSetupActions } from '../components/research/ResearchSetupPanel';
import ResearchAnalysisPanel, { ResearchAnalysisActions } from '../components/research/ResearchAnalysisPanel';
import BoardPageShell from '../components/board/BoardPageShell';
import { useBoardCoordinates } from '../components/board/useBoardCoordinates';
import ModulePlate from '../components/layout/ModulePlate';
import { useResearchBoard } from '../hooks/useResearchBoard';
import { useResearchSession } from '../../hooks/useResearchSession';
import { useTranslation } from '../../hooks/useTranslation';
import { API, authHeaders } from '../../api';
import { KifuAPI } from '../../api/kifuApi';
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

    /* 轮询失败要说出来。原来这里是 catch {} 静静吞掉，界面就永远停在
       「正在连接研究会话…」的不确定进度条上 —— 2026-08-21 测试服那次「一直卡住」
       就是这个样子：每秒一次 401，用户看不到任何线索。
       连续失败若干次才报，避免一次抖动就弹错。 */
    const progressFailRef = useRef(0);
    const [progressError, setProgressError] = useState<string | null>(null);
    const PROGRESS_FAIL_LIMIT = 5;

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
        }, token || undefined).then((result) => {
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
    }, [l1ShowHints, l1ShowTerritory, l1PositionKey, isAnalyzing, token]); // eslint-disable-line react-hooks/exhaustive-deps

    const handleL1ToggleHints = useCallback(() => setL1ShowHints(prev => !prev), []);
    const handleL1ToggleTerritory = useCallback(() => setL1ShowTerritory(prev => !prev), []);

    // Research session hook (L2)
    const session = useResearchSession({ token: token || undefined });

    // Analysis toggles for Legacy Board (L2)
    const [analysisToggles, setAnalysisToggles] = useState<Record<string, boolean>>({
        hints: false,
        ownership: false,
        policy: false,
        eval: false,
        numbers: false,
        children: false,
    });

    // spec §3.2：**棋盘边长低于 500px 时坐标默认关闭**，判据是棋盘量出来的边长而不是视口宽度
    // （899px 横窗堆叠后棋盘仍可能大于 500）。原来这一页有三个各说各话的真相来源：
    // 初值里的 `coords: true`（共享 Board 真的读它，见 Board.tsx:194）和两处写死的坐标开。
    // 现在只剩这一个。本页三个形态一次只渲染一个，所以共用一份 edge 状态。
    const [boardEdge, setBoardEdge] = useState(0);
    const coordinates = useBoardCoordinates(boardEdge);

    const toggleAnalysis = useCallback((key: string) => {
        setAnalysisToggles(prev => ({ ...prev, [key]: !prev[key] }));
    }, []);

    // beforeunload: cleanup session when user closes tab/navigates away
    useEffect(() => {
        const cleanup = () => {
            if (session.sessionId) {
                // Use fetch with keepalive for reliable cleanup on page unload
                // 带上身份：会话归属校验认的是 current_user.id（见 useResearchSession 那段注释）
                fetch(`/api/session/${session.sessionId}`, { method: 'DELETE', keepalive: true, headers: authHeaders() }).catch(() => {});
            }
        };
        window.addEventListener('beforeunload', cleanup);
        return () => window.removeEventListener('beforeunload', cleanup);
    }, [session.sessionId]);

    // Deep linking: load kifu from ?kifu_id=xxx query param
    const kifuLoadedRef = useRef(false);
    /* `?analyze=1` 不在这条 effect 里直接开分析，而是先立一个标志、等下一帧再开。
       原因见下面那条 effect 的注释 —— 这里直接开会拿一张空棋盘去分析。 */
    const [autoAnalyzeAfterLoad, setAutoAnalyzeAfterLoad] = useState(false);
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
                    setAutoAnalyzeAfterLoad(true);
                }
            })
            .catch((err) => {
                console.error('Failed to load kifu for deep link:', err);
            });
    }, [searchParams]); // eslint-disable-line react-hooks/exhaustive-deps

    /* `?kifu_id=…&analyze=1` 的自动分析在这里发，不在上面那条 effect 里。

       改之前是 `setTimeout(() => handleStartAnalysis(), 100)`，那是错的，而且
       **不是等得不够久**：`setTimeout` 的闭包捕获的是 effect 那一帧的
       `handleStartAnalysis`，那一帧的 `board.moves` / `board.currentMove` /
       `board.getSnapshot()` 全是加载前的空值（`loadFromSGF` 走 `useState`，
       同一段 async 续体里还没冲刷）。于是 `handleStartAnalysis` 里那行
       `board.moves.length > 0 ? sgf : undefined` 取到 `undefined` —— 会话建成
       一张空棋盘，紧跟着的 `analysisScan(500)` 扫的也是空棋盘。等 1000ms 一样错，
       因为拿到的那个函数本身就是旧的。

       改成「立标志 + 独立 effect」之后，这条 effect 只在标志变 true 的那一帧之后
       才跑，而 `setAutoAnalyzeAfterLoad(true)` 与 `loadFromSGF` 的 setState 在同一段
       续体里、由 React 一起冲刷，所以这一帧的 `handleStartAnalysis` 读到的是**装好的**
       棋盘。顺带把 `getSnapshot()` 和 `initialMove` 两处同样读旧值的地方一起修好了 ——
       它们和 SGF 是同一个闭包里的三个受害者，只补 SGF 那一个是补不干净的。

       同族：`?user_game_id=` 那条从一开始就不认 `analyze=1`（全盘扫描是计费动作，
       不该由一次导航悄悄触发），所以它没有这个坑。 */
    useEffect(() => {
        if (!autoAnalyzeAfterLoad) return;
        setAutoAnalyzeAfterLoad(false);
        void handleStartAnalysis();
    }, [autoAnalyzeAfterLoad]); // eslint-disable-line react-hooks/exhaustive-deps

    /* 「进入研究室」的入口：`?user_game_id=<uuid>`（复盘·报告详情页 → 这里）。
       Fan 2026-08-22 点头补上 —— 在此之前报告页那个按钮只 `navigate('/galaxy/research')`，
       落到一张空棋盘。

       和上面那条 `?kifu_id=` 是**两个 id 空间**：那条走棋谱库 `KifuAPI.getAlbum`，
       这条走个人对局 `UserGamesAPI.get`（要 token，而 auth 是异步加载的，所以
       `!token` 时先不烧掉 ref，等 token 到了这个 effect 会因为依赖变化再跑一次）。

       **不认 `&analyze=1`。** 全盘扫描是计费动作，不该由一次导航悄悄触发；报告页那一局
       也早已分析过。要分析就按「开始研究」。上面 kifu 那条认它，是它原有的行为，不动。

       SGF 用刚取回来的 `detail.sgf_content`，不从 `board` 反推 —— `loadFromSGF` 的
       setState 在同一段 async 续体里还没冲刷，此刻读 `board.moves` 拿到的是加载前的空值。
       （kiosk 那份同名页在 `ResearchPage.tsx:374` 的注释里记的就是这个坑。） */
    const userGameLoadedRef = useRef(false);
    useEffect(() => {
        const userGameId = searchParams.get('user_game_id');
        if (!userGameId || userGameLoadedRef.current || !token) return;
        userGameLoadedRef.current = true;

        UserGamesAPI.get(token, userGameId)
            .then((detail) => {
                if (!detail.sgf_content) return;
                const result = board.loadFromSGF(detail.sgf_content);
                if (!result.success) {
                    console.error('Failed to load user game for deep link:', result.error);
                }
            })
            .catch((err) => {
                console.error('Failed to load user game for deep link:', err);
            });
    }, [searchParams, token]); // eslint-disable-line react-hooks/exhaustive-deps

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
                    progressFailRef.current = 0;
                    setProgressError(null);
                }
            } catch (err) {
                progressFailRef.current += 1;
                if (progressFailRef.current >= PROGRESS_FAIL_LIMIT) {
                    const status = (err as { status?: number })?.status;
                    setProgressError(status ? `HTTP ${status}` : String((err as Error)?.message ?? err));
                }
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
            setProgressError(null);
            progressFailRef.current = 0;
            setEtaSeconds(null);
            analysisStartRef.current = null;
            hintsEnabledRef.current = false;
            setIsAnalyzing(true);
            // 5. Trigger full analysis scan (500 visits per node, engine queues internally)
            API.analysisScan(newSessionId, 500);
        }
    }, [board, session]);

    /* 重试：把失败计数清零并重新发一次全盘扫描；轮询本身一直在跑，
       下一拍拿到 200 就会自己把错误条收掉。 */
    const handleRetryProgress = useCallback(() => {
        progressFailRef.current = 0;
        setProgressError(null);
        const sid = activeSessionIdRef.current;
        if (sid) API.analysisScan(sid, 500).catch(() => {});
    }, []);

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
        setProgressError(null);
        progressFailRef.current = 0;
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

    /* ══════════════════════════════════════════════════════════════════
       统一版式：三个形态都走 BoardPageShell 的三段右栏
         模块牌（不滚）/ 中段（唯一可滚）/ 动作区（不滚）
       棋盘上方不留任何东西 —— 原来压在棋盘头上的「研究模式 + 返回编辑」
       那一条，标题进模块牌、按钮进动作区。
       研究是一级导航，没有上一级，所以模块牌不出返回键。
       文案一律复用已有词条，本轮不新增 i18n key（原型里那两个状态 chip
       「编辑中 / 分析完成」需要新词条，暂缺，副标题已经把状态说清楚了）。
       ══════════════════════════════════════════════════════════════════ */

    // ──────────────────────────── L2: Analysis Mode (complete) ────────────────────────────
    if (isAnalyzing && analysisComplete && session.gameState) {
        const gs = session.gameState;
        const totalMoves = gs.history.length - 1; // exclude root
        const currentMove = gs.current_node_index;

        return (
            <>
                <BoardPageShell
                    onBoardSizeChange={setBoardEdge}
                    board={(
                        <Board
                            gameState={gs}
                            onMove={session.onMove}
                            analysisToggles={{ ...analysisToggles, coords: coordinates.visible }}
                        />
                    )}
                    modulePlate={(
                        <ModulePlate
                            title={t('Research', '研究')}
                            subtitle={`${t('research:mode', '研究模式')} · ${t('research:move_counter', '{current} / {total} 手').replace('{current}', String(currentMove)).replace('{total}', String(totalMoves))}`}
                            backTo="/galaxy/research"
                            showBack={false}
                        />
                    )}
                    railBody={(
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
                    )}
                    actions={(
                        <>
                            <ResearchAnalysisActions
                                currentMove={currentMove}
                                totalMoves={totalMoves}
                                onMoveChange={handleL2MoveChange}
                            />
                            <Box sx={{ px: 2, pb: 1.5 }}>
                                <Button
                                    fullWidth
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
                        </>
                    )}
                />
                <GameLibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} onLoadGame={handleLoadFromLibrary} />
            </>
        );
    }

    // ──────────────────────────── L2: Analysis in Progress ────────────────────────────
    // 以前这里整屏换成一个居中的转圈；现在盘面留在左边不动，进度进右栏中段 ——
    // 分析在后台跑，随时可以看着盘面等，取消也还在原地。
    if (isAnalyzing) {
        const progressPercent = analysisProgress && analysisProgress.total > 0
            ? Math.round((analysisProgress.analyzed / analysisProgress.total) * 100)
            : 0;

        return (
            <>
                <BoardPageShell
                    onBoardSizeChange={setBoardEdge}
                    board={(
                        <LiveBoard
                            moves={board.moves}
                            stoneColors={board.stoneColors}
                            currentMove={board.currentMove}
                            boardSize={board.boardSize}
                            showCoordinates={coordinates.visible}
                            showMoveNumbers={board.showMoveNumbers}
                            handicapCount={board.handicapCount}
                            minimumCanvasSize={0}
                            minContainerHeight={0}
                        />
                    )}
                    modulePlate={(
                        <ModulePlate
                            title={t('Research', '研究')}
                            subtitle={t('research:analyzing_game', '正在分析棋局')}
                            backTo="/galaxy/research"
                            showBack={false}
                        />
                    )}
                    railBody={(
                        <Box sx={{ p: 2 }}>
                            {progressError && (
                                <Alert
                                    severity="error"
                                    sx={{ mb: 2 }}
                                    action={(
                                        <Button color="inherit" size="small" onClick={handleRetryProgress}>
                                            {t('common:retry', '重试')}
                                        </Button>
                                    )}
                                >
                                    {t('research:progress_failed', '无法获取分析进度')} · {progressError}
                                </Alert>
                            )}
                            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                                {analysisProgress
                                    ? t('research:progress', '已完成 {analyzed} / {total} 步').replace('{analyzed}', String(analysisProgress.analyzed)).replace('{total}', String(analysisProgress.total))
                                    : t('research:connecting', '正在连接研究会话...')
                                }
                            </Typography>

                            <LinearProgress
                                variant={analysisProgress ? 'determinate' : 'indeterminate'}
                                value={progressPercent}
                                sx={{
                                    height: 10,
                                    borderRadius: 5,
                                    bgcolor: 'rgba(255,255,255,0.1)',
                                    '& .MuiLinearProgress-bar': { borderRadius: 5, bgcolor: 'primary.main' },
                                }}
                            />

                            {analysisProgress && (
                                <Box sx={{ mt: 1.5 }}>
                                    <Typography variant="body2" color="primary.main" sx={{ fontWeight: 700, fontFamily: (t) => `"IBM Plex Mono", monospace, ${t.typography.fontFamily}` }}>
                                        {progressPercent}%
                                    </Typography>
                                    {etaSeconds !== null && etaSeconds > 0 && (
                                        <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5, fontFamily: (t) => `"IBM Plex Mono", monospace, ${t.typography.fontFamily}` }}>
                                            {t('research:eta', '预计剩余 {time}').replace('{time}',
                                                etaSeconds >= 60
                                                    ? t('research:time_min_sec', '{min}分{sec}秒').replace('{min}', String(Math.floor(etaSeconds / 60))).replace('{sec}', (etaSeconds % 60).toString().padStart(2, '0'))
                                                    : t('research:time_sec', '{sec}秒').replace('{sec}', String(etaSeconds))
                                            )}
                                        </Typography>
                                    )}
                                </Box>
                            )}
                        </Box>
                    )}
                    actions={(
                        <Box sx={{ p: 2 }}>
                            <Button
                                fullWidth
                                size="small"
                                color="error"
                                variant="outlined"
                                onClick={handleReturnToEdit}
                                sx={{ textTransform: 'none' }}
                            >
                                {t('research:cancel', '取消')}
                            </Button>
                        </Box>
                    )}
                />
                <GameLibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} onLoadGame={handleLoadFromLibrary} />
            </>
        );
    }

    // ──────────────────────────── L1: Setup / Edit Mode ────────────────────────────
    return (
        <>
            <BoardPageShell
                    onBoardSizeChange={setBoardEdge}
                board={(
                    <LiveBoard
                        moves={board.moves}
                        stoneColors={board.stoneColors}
                        currentMove={board.currentMove}
                        boardSize={board.boardSize}
                        showCoordinates={coordinates.visible}
                        showMoveNumbers={board.showMoveNumbers}
                        handicapCount={board.handicapCount}
                        onIntersectionClick={board.handleIntersectionClick}
                        nextColor={board.nextColor ?? undefined}
                        aiMarkers={l1ShowHints ? l1AiMarkers : null}
                        showAiMarkers={l1ShowHints}
                        showTerritory={l1ShowTerritory}
                        ownership={l1Ownership}
                        minimumCanvasSize={0}
                        minContainerHeight={0}
                    />
                )}
                modulePlate={(
                    <ModulePlate
                        title={t('Research', '研究')}
                        subtitle={t('research:move_counter', '{current} / {total} 手').replace('{current}', String(Math.max(0, board.currentMove - board.handicapCount))).replace('{total}', String(board.moves.length - board.handicapCount))}
                        backTo="/galaxy/research"
                        showBack={false}
                    />
                )}
                railBody={(
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
                    />
                )}
                actions={(
                    <>
                        {/* 原来贴在棋盘下面那条走子键，按契约进动作区 */}
                        <Box sx={{
                            px: 2,
                            py: 1,
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
                                    mx: 1,
                                    fontFamily: (t) => `"IBM Plex Mono", monospace, ${t.typography.fontFamily}`,
                                    color: 'text.secondary',
                                    minWidth: 76,
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
                        <ResearchSetupActions onStartAnalysis={handleStartAnalysis} />
                    </>
                )}
            />
            <GameLibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} onLoadGame={handleLoadFromLibrary} />
        </>
    );
};

export default ResearchPage;
