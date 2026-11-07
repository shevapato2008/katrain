import { useState, useCallback, useRef, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Alert, Box, Typography, Button } from '@mui/material';
import LiveBoard, { type AiMoveMarker } from '../../components/live/LiveBoard';
import ResearchSetupPanel from '../components/research/ResearchSetupPanel';
import BoardPageShell from '../components/board/BoardPageShell';
import { useBoardCoordinates } from '../components/board/useBoardCoordinates';
import ModulePlate from '../components/layout/ModulePlate';
import { useResearchBoard } from '../hooks/useResearchBoard';
import { useSound } from '../../hooks/useSound';
import { isReplayStoneMove } from '../../hooks/useReplayStoneSound';
import { useTranslation } from '../../hooks/useTranslation';
import { KifuAPI } from '../../api/kifuApi';
import { UserGamesAPI } from '../api/userGamesApi';
import GameLibraryModal from '../components/research/CloudSGFPanel';
import { useAuth } from '../../context/AuthContext';
import AuthRequiredDialog from '../components/auth/AuthRequiredDialog';
import { accessAllowed } from '../../components/auth/accessPolicy';
import { usePaidPosition } from '../../features/analysis/usePaidPosition';
import { useReportTasks } from '../../features/report/useReportTasks';
import { ConsumptionQuoteDialog } from '../../features/membership/ConsumptionQuoteDialog';
import { membershipErrorCode, membershipErrorText, type MembershipErrorCode } from '../../features/membership/presentation';

const ResearchPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const { token, status, identityKey, isGuest, isAuthenticated } = useAuth();
    const { t, lang } = useTranslation();
    const board = useResearchBoard();
    const { play } = useSound();
    const [authPromptOpen, setAuthPromptOpen] = useState(false);
    const [libraryOpen, setLibraryOpen] = useState(false);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [reportPreparationError, setReportPreparationError] = useState<MembershipErrorCode | null>(null);
    const [reportBusy, setReportBusy] = useState(false);
    const [boardEdge, setBoardEdge] = useState(0);
    const coordinates = useBoardCoordinates(boardEdge);
    const positionSgf = board.serializeToSGF({ position: true }).sgf;
    const paid = usePaidPosition({ token, status, identityKey, snapshotKey: positionSgf, input: { sgf: positionSgf } });
    const { createReport, pendingQuote: reportQuote, quoteBusy, confirmQuote, cancelQuote, error: reportError, billingError: reportBillingError } = useReportTasks(token, isAuthenticated, identityKey, status);
    const l1ShowHints = paid.showHints && !!paid.result;
    const l1ShowTerritory = paid.showOwnership && !!paid.result;
    const l1AnalysisPending = paid.busy;
    const l1AiMarkers: AiMoveMarker[] | null = paid.result?.moves.slice(0, 5).map((move, index) => ({
        move: move.move, rank: index + 1, visits: move.visits, winrate: move.winrate, score_lead: move.score_lead,
    })) ?? null;
    const l1Ownership = paid.result?.ownership.length === board.boardSize * board.boardSize
        ? Array.from({ length: board.boardSize }, (_, y) => paid.result!.ownership.slice(y * board.boardSize, (y + 1) * board.boardSize)) : null;
    const handleL1ToggleHints = useCallback(() => { void paid.toggle('hints'); }, [paid.toggle]);
    const handleL1ToggleTerritory = useCallback(() => { void paid.toggle('ownership'); }, [paid.toggle]);
    const handleL1Intersection = useCallback((x: number, y: number) => {
        if (board.handleIntersectionClick(x, y)) play('stone');
    }, [board, play]);
    const handleL1MoveChange = useCallback((move: number) => {
        const target = Math.max(board.handicapCount, Math.min(board.moves.length, move));
        if (target === board.currentMove) return;
        board.handleMoveChange(target);
        if (target > board.handicapCount && isReplayStoneMove(board.moves[target - 1], board.boardSize)) play('stone');
    }, [board, play]);
    const liveIdentity = useRef(identityKey);
    liveIdentity.current = identityKey;
    const saveBoard = useCallback(async () => {
        const { sgf } = board.serializeToSGF();
        return UserGamesAPI.create(token, { sgf_content: sgf, source: 'research', category: 'game',
            player_black: board.playerBlack || undefined, player_white: board.playerWhite || undefined,
            board_size: board.boardSize, rules: board.rules, komi: board.komi, move_count: board.moves.length });
    }, [board, token]);
    const handleSaveToCloud = useCallback(async () => {
        if (!isAuthenticated) { setAuthPromptOpen(true); return; }
        setSaveError(null); setReportPreparationError(null);
        try { await saveBoard(); } catch (error) { setSaveError(error instanceof Error ? error.message : '保存失败'); }
    }, [isAuthenticated, saveBoard]);
    const handleCreateReport = useCallback(async () => {
        if (!isAuthenticated || status !== 'authenticated') { setAuthPromptOpen(true); return; }
        if (reportBusy) return;
        const requestedIdentity = identityKey;
        setReportBusy(true); setSaveError(null); setReportPreparationError(null);
        try {
            const game = await saveBoard();
            if (liveIdentity.current !== requestedIdentity) return;
            const task = await createReport({ userGameId: game.id, totalMoves: game.move_count });
            if (task && liveIdentity.current === requestedIdentity) navigate('/report');
        } catch (error) { if (liveIdentity.current === requestedIdentity) setReportPreparationError(membershipErrorCode(error, 'report_failed')); }
        finally { setReportBusy(false); }
    }, [createReport, identityKey, isAuthenticated, navigate, reportBusy, saveBoard, status]);
    const handleOpenFromCloud = useCallback(() => setLibraryOpen(true), []);
    const handleLoadFromLibrary = useCallback((sgf: string) => { board.loadFromSGF(sgf); }, [board]);
    // Deep linking: load kifu from ?kifu_id=xxx query param
    const kifuLoadedRef = useRef<string | null>(null);
    const kifuRequestRef = useRef(0);
    const lastKifuPlayersRef = useRef<{ id: string; black: string; white: string } | null>(null);
    const currentPlayersRef = useRef({ black: board.playerBlack, white: board.playerWhite });
    useEffect(() => {
        currentPlayersRef.current = { black: board.playerBlack, white: board.playerWhite };
    }, [board.playerBlack, board.playerWhite]);
    useEffect(() => {
        const kifuId = searchParams.get('kifu_id');
        if (!kifuId) return;
        const request = ++kifuRequestRef.current;

        KifuAPI.getAlbum(Number(kifuId), lang)
            .then((album) => {
                if (request !== kifuRequestRef.current) return;
                const firstLoad = kifuLoadedRef.current !== kifuId;
                if (firstLoad && album.sgf_content) {
                    board.loadFromSGF(album.sgf_content);
                    kifuLoadedRef.current = kifuId;
                }
                const black = album.display_player_black ?? t('game:black_side', '黑方');
                const white = album.display_player_white ?? t('game:white_side', '白方');
                const previous = lastKifuPlayersRef.current;
                if (firstLoad || previous?.id !== kifuId || currentPlayersRef.current.black === previous.black) board.setPlayerBlack(black);
                if (firstLoad || previous?.id !== kifuId || currentPlayersRef.current.white === previous.white) board.setPlayerWhite(white);
                lastKifuPlayersRef.current = { id: kifuId, black, white };


            })
            .catch((err) => {
                if (request === kifuRequestRef.current) console.error('Failed to load kifu for deep link:', err);
            });
        return () => { kifuRequestRef.current += 1; };
    }, [searchParams, lang]); // eslint-disable-line react-hooks/exhaustive-deps

    /* 「进入研究室」的入口：`?user_game_id=<uuid>`（复盘·报告详情页 → 这里）。
       Fan 2026-08-22 点头补上 —— 在此之前报告页那个按钮只 `navigate('/research')`，
       落到一张空棋盘。

       和上面那条 `?kifu_id=` 是**两个 id 空间**：那条走棋谱库 `KifuAPI.getAlbum`，
       这条走个人对局 `UserGamesAPI.get`，必须等 /me 确认身份；保留的 token 不代表
       已确认登录，而 cookie 身份可以没有 token。加载结果归属发出请求时的身份，
       退出、切号或卸载后不能再装进棋盘。

       **不认 `&analyze=1`。** 全盘扫描是计费动作，不该由一次导航悄悄触发；报告页那一局
       也早已分析过。要分析就按「开始研究」。上面 kifu 那条认它，是它原有的行为，不动。

       SGF 用刚取回来的 `detail.sgf_content`，不从 `board` 反推 —— `loadFromSGF` 的
       setState 在同一段 async 续体里还没冲刷，此刻读 `board.moves` 拿到的是加载前的空值。
       （kiosk 那份同名页在 `ResearchPage.tsx:374` 的注释里记的就是这个坑。） */
    const userGameId = searchParams.get('user_game_id');
    const privateGameAllowed = accessAllowed(status, isAuthenticated, isGuest, false) && !!identityKey;
    const userGameScope = privateGameAllowed && userGameId ? `${identityKey}:${userGameId}` : null;
    const userGameScopeRef = useRef(userGameScope);
    userGameScopeRef.current = userGameScope;
    const userGameLoadedRef = useRef<string | null>(null);
    useEffect(() => {
        if (!userGameId || !userGameScope || userGameLoadedRef.current === userGameScope) return;
        let cancelled = false;
        const current = () => !cancelled && userGameScopeRef.current === userGameScope;

        UserGamesAPI.get(token, userGameId)
            .then((detail) => {
                if (!current()) return;
                userGameLoadedRef.current = userGameScope;
                if (!detail.sgf_content) return;
                const result = board.loadFromSGF(detail.sgf_content);
                if (!result.success) {
                    console.error('Failed to load user game for deep link:', result.error);
                }
            })
            .catch((err) => {
                if (!current()) return;
                console.error('Failed to load user game for deep link:', err);
            });
        return () => { cancelled = true; };
    }, [userGameId, userGameScope, token]); // eslint-disable-line react-hooks/exhaustive-deps

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
                        onIntersectionClick={handleL1Intersection}
                        rejectOccupiedIntersections={!board.editMode}
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
                        backTo="/research"
                        showBack={false}
                    />
                )}
                railBody={(
                    <>
                    {board.editedSetup && <Alert severity="info" sx={{ mb: 1 }}>{t('research:new_setup_notice', '摆子编辑已建立新局面，原行棋历史已清除。')}</Alert>}
                    {(paid.error || reportError || reportPreparationError || saveError) && <Alert severity="error" sx={{ mb: 1 }}>{paid.error || reportError || (reportPreparationError ? membershipErrorText(reportPreparationError, t) : saveError)}</Alert>}
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
                    </>
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
                                disabled={board.currentMove <= board.handicapCount}
                                onClick={() => handleL1MoveChange(0)}
                                sx={{ minWidth: 32, color: 'text.secondary' }}
                            >
                                ⏮
                            </Button>
                            <Button
                                size="small"
                                disabled={board.currentMove <= board.handicapCount}
                                onClick={() => handleL1MoveChange(board.currentMove - 1)}
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
                                onClick={() => handleL1MoveChange(board.currentMove + 1)}
                                sx={{ minWidth: 32, color: 'text.secondary' }}
                            >
                                ▶
                            </Button>
                            <Button
                                size="small"
                                disabled={board.currentMove >= board.moves.length}
                                onClick={() => handleL1MoveChange(board.moves.length)}
                                sx={{ minWidth: 32, color: 'text.secondary' }}
                            >
                                ⏭
                            </Button>
                        </Box>
                        <Box sx={{ p: 2 }}><Button fullWidth variant="contained" size="large" onClick={() => void handleCreateReport()} disabled={reportBusy}>
                            {t('membership:create_report', '创建复盘报告')}
                        </Button></Box>
                    </>
                )}
            />
            <ConsumptionQuoteDialog quote={paid.pendingQuote} busy={paid.busy} error={paid.error} onCancel={paid.cancel} onConfirm={() => void paid.confirm()} />
            <ConsumptionQuoteDialog quote={reportQuote?.quote ?? null} busy={quoteBusy} error={reportBillingError ? reportError : null} onCancel={cancelQuote}
                onConfirm={() => { void confirmQuote().then((task) => { if (task) navigate('/report'); }).catch(() => undefined); }} />
            <GameLibraryModal open={libraryOpen} onClose={() => setLibraryOpen(false)} onLoadGame={handleLoadFromLibrary} />
            <AuthRequiredDialog
                open={authPromptOpen}
                onClose={() => setAuthPromptOpen(false)}
                message={t('research:login_required', '全盘分析要用云端引擎，需要登录后才能使用。摆棋和打谱不需要登录。')}
            />
        </>
    );
};

export default ResearchPage;
