import { useEffect, useState, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, CircularProgress, Alert, Chip, Button, Dialog, DialogTitle, DialogContent, DialogContentText, DialogActions } from '@mui/material';
import Board from '../../components/Board';
import type { BoardProps } from '../../components/Board';
import { useGameSession } from '../../hooks/useGameSession';

type Board3DComponent = React.ComponentType<BoardProps>;
import RightSidebarPanel, { RightSidebarActions } from '../components/game/RightSidebarPanel';
import BoardPageShell from '../components/board/BoardPageShell';
import ModulePlate from '../components/layout/ModulePlate';
import { isRankedGameType } from '../../features/aiLadder/gameType';
import { useAuth } from '../../context/AuthContext';
import { useGameNavigation } from '../context/GameNavigationContext';
import { API } from '../../api';
import { useTranslation } from '../../hooks/useTranslation';
import { translateResult } from '../../utils/resultTranslation';

const GameRoomPage = () => {
    const { sessionId } = useParams();
    const { user, token } = useAuth();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { registerActiveGame, unregisterActiveGame } = useGameNavigation();
    /* 坐标 / 手数 / 落子特效这三个开关原来是**死的**：面板照一个写死的字面量渲染，
       `onToggleChange` 对它们是空操作，而棋盘拿到的又是另一个写死的
       `{ coords: true, numbers: false }`。点了没有任何反应 —— 控件账本里的空按钮。
       改成真状态，并且**同一个对象**同时喂给面板和棋盘，两边不可能再各说各的。 */
    const [displayToggles, setDisplayToggles] = useState({
        coords: true,
        numbers: false,
        stoneDropEffect: false,
        view3d: false,
    });
    const view3d = displayToggles.view3d;
    const [Board3D, setBoard3D] = useState<Board3DComponent | null>(null);
    const board3dLoadingRef = useRef(false);

    useEffect(() => {
        if (view3d && !Board3D && !board3dLoadingRef.current) {
            board3dLoadingRef.current = true;
            import('../../components/Board3D').then(mod => {
                setBoard3D(() => mod.default);
            });
        }
    }, [view3d, Board3D]);

    const handleToggleChange = useCallback((setting: string) => {
        if (setting !== 'coords' && setting !== 'numbers' && setting !== 'stoneDropEffect' && setting !== 'view3d') return;
        setDisplayToggles(prev => {
            const next = { ...prev, [setting]: !prev[setting] };
            if (setting === 'view3d') localStorage.setItem('katrain_view3d', String(next.view3d));
            return next;
        });
    }, []);

    const [showLeaveConfirm, setShowLeaveConfirm] = useState(false);
    const [showGameEndDialog, setShowGameEndDialog] = useState(false);
    const [showResignConfirm, setShowResignConfirm] = useState(false);
    const [showCountConfirm, setShowCountConfirm] = useState(false);
    const [showCountRequestDialog, setShowCountRequestDialog] = useState(false);
    const [countRequesterName, setCountRequesterName] = useState<string>('');

    const handleGameEnd = useCallback(() => {
        setShowGameEndDialog(true);
    }, []);

    const handleCountRequest = useCallback((data: { requester_id: number; requester_name: string }) => {
        // Only show dialog if we're not the requester
        if (data.requester_id !== user?.id) {
            setCountRequesterName(data.requester_name);
            setShowCountRequestDialog(true);
        }
    }, [user?.id]);

    const handleCountRejected = useCallback(() => {
        alert(t('count_rejected_msg', 'Your counting request was rejected.'));
    }, [t]);

    const handleCountTimeout = useCallback(() => {
        setShowCountRequestDialog(false);
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
    } = useGameSession({
        token: token || undefined,
        onGameEnd: handleGameEnd,
        onCountRequest: handleCountRequest,
        onCountRejected: handleCountRejected,
        onCountTimeout: handleCountTimeout
    });

    useEffect(() => {
        if (sessionId && sessionId !== currentSessionId) {
            setSessionId(sessionId);
        }
    }, [sessionId, currentSessionId, setSessionId]);

    // Register/unregister active game for sidebar navigation protection
    useEffect(() => {
        const isBlack = gameState?.players_info.B.name === user?.username;
        const isWhite = gameState?.players_info.W.name === user?.username;
        const isPlayer = isBlack || isWhite;

        if (gameState && isPlayer && !gameState.end_result && !gameEndData) {
            registerActiveGame(async () => {
                if (sessionId && token) {
                    try {
                        await API.leaveMultiplayerGame(sessionId, token);
                    } catch (e) {
                        console.error("Failed to leave game:", e);
                    }
                }
            });
        } else {
            unregisterActiveGame();
        }
        return () => unregisterActiveGame();
    }, [gameState?.end_result, gameState?.players_info, gameEndData, user?.username, sessionId, token, registerActiveGame, unregisterActiveGame]);

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
        } else if (action === 'count') {
             if (!gameState?.end_result) {
                 setShowCountConfirm(true);
             }
        } else {
             void (async () => { try { await handleAction(action); } catch { /* surfaced by hook */ } })();
        }
    }, [handleAction, gameState?.end_result]);

    const confirmCount = useCallback(async () => {
        setShowCountConfirm(false);
        if (!sessionId || !token) return;
        try {
            const response = await API.requestCount(sessionId, token);
            if (response.result) {
                // Count completed immediately (e.g., other player already requested)
                setShowGameEndDialog(true);
            }
            // If status is 'pending', wait for response via WebSocket
        } catch (e: any) {
            console.error("Count request failed:", e);
            alert(e.message || "Count request failed");
        }
    }, [sessionId, token]);

    const respondToCountRequest = useCallback(async (accept: boolean) => {
        setShowCountRequestDialog(false);
        if (!sessionId || !token) return;
        try {
            await API.respondCount(sessionId, accept, token);
        } catch (e: any) {
            console.error("Count response failed:", e);
        }
    }, [sessionId, token]);

    const confirmResign = useCallback(async () => {
        setShowResignConfirm(false);
        try { await handleAction('resign'); } catch { /* surfaced by hook */ }
    }, [handleAction]);

    if (error) return <Box sx={{ p: 4 }}><Alert severity="error">{error}</Alert><Button onClick={() => navigate('/galaxy/play/human')}>{t('game_room:back_to_lobby', '返回大厅')}</Button></Box>;
    if (!gameState) return <Box sx={{ p: 4, display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%' }}><CircularProgress /></Box>;

    const isBlack = gameState.players_info.B.name === user?.username;
    const isWhite = gameState.players_info.W.name === user?.username;
    const isPlayer = isBlack || isWhite;
    const myTurn = (gameState.player_to_move === 'B' && isBlack) || (gameState.player_to_move === 'W' && isWhite);

    const spectatorCount = gameState.sockets_count !== undefined ? Math.max(0, gameState.sockets_count - 2) : 0;
    const isGameOver = !!gameState.end_result;

    /* 「离开对局」的落点。观战者没有可判负的东西、已结束的对局也没有 —— 直接回大厅；
       只有进行中的自己的对局才弹那句「离开将判负」的确认框。 */
    const handleLeave = () => {
        if (!isPlayer || isGameOver || gameEndData) {
            navigate('/galaxy/play/human');
        } else {
            setShowLeaveConfirm(true);
        }
    };


    // Determine game end result message
    const getGameEndMessage = () => {
        if (!gameEndData) return "";
        const { reason, winner_id, result } = gameEndData;
        const isWinner = winner_id === user?.id;

        if (reason === 'forfeit') {
            return isWinner ? t('game_end:forfeit_win', "Your opponent left the game. You win!") : t('game_end:forfeit_loss', "You forfeited the game.");
        } else if (reason === 'resign') {
            return isWinner ? t('game_end:resign_win', "Your opponent resigned. You win!") : t('game_end:resign_loss', "You resigned.");
        } else if (reason === 'timeout') {
            return isWinner ? t('game_end:timeout_win', "Your opponent ran out of time. You win!") : t('game_end:timeout_loss', "You ran out of time.");
        } else if (reason === 'count') {
            return t('game_end:count', 'Game ended by counting: {result}').replace('{result}', translateResult(result, t, gameState?.ruleset));
        } else {
            return t(result || "Game ended", result || "Game ended");
        }
    };

    return (
        <Box sx={{ display: 'flex', height: '100%', minHeight: 0, overflow: 'hidden' }}>
            {/* Leave Confirmation Dialog */}
            <Dialog open={showLeaveConfirm} onClose={() => setShowLeaveConfirm(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('leave_game_title', 'Leave Game?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('game_room:forfeit_warning', 'Leaving the game will count as a forfeit. Your opponent will win this game. Are you sure you want to leave?')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowLeaveConfirm(false)}>{t('cancel', 'Cancel')}</Button>
                    <Button onClick={handleLeaveGame} color="error" variant="contained">{t('game_room:leave_forfeit', 'Leave & Forfeit')}</Button>
                </DialogActions>
            </Dialog>

            {/* Resign Confirmation Dialog */}
            <Dialog open={showResignConfirm} onClose={() => setShowResignConfirm(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('resign_game_title', 'Resign Game?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('resign_confirm_text', 'Are you sure you want to resign?')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowResignConfirm(false)}>{t('cancel', 'Cancel')}</Button>
                    <Button onClick={confirmResign} color="error" variant="contained">{t('RESIGN', 'Resign')}</Button>
                </DialogActions>
            </Dialog>

            {/* Game End Dialog */}
            <Dialog open={showGameEndDialog} onClose={handleBackToLobby} maxWidth="xs" fullWidth>
                <DialogTitle>{t('Game Over', 'Game Over')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {getGameEndMessage()}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={handleBackToLobby} variant="contained" color="primary">{t('game_room:back_to_lobby', 'Back to Lobby')}</Button>
                </DialogActions>
            </Dialog>

            {/* Count Confirmation Dialog - for initiator */}
            <Dialog open={showCountConfirm} onClose={() => setShowCountConfirm(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('count_confirm_title', 'End Game by Counting?')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('count_confirm_text', 'Calculate the final score to end the game.')}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => setShowCountConfirm(false)}>{t('cancel', 'Cancel')}</Button>
                    <Button onClick={confirmCount} color="primary" variant="contained">{t('COUNT', 'Count')}</Button>
                </DialogActions>
            </Dialog>

            {/* Count Request Dialog - for responder */}
            <Dialog open={showCountRequestDialog} onClose={() => setShowCountRequestDialog(false)} maxWidth="xs" fullWidth>
                <DialogTitle>{t('count_request_title', 'Counting Request')}</DialogTitle>
                <DialogContent>
                    <DialogContentText>
                        {t('count_request_text', '{name} wants to end the game by counting. Do you agree?').replace('{name}', countRequesterName)}
                    </DialogContentText>
                </DialogContent>
                <DialogActions>
                    <Button onClick={() => respondToCountRequest(false)} color="error">{t('reject', 'Reject')}</Button>
                    <Button onClick={() => respondToCountRequest(true)} color="primary" variant="contained">{t('accept', 'Accept')}</Button>
                </DialogActions>
            </Dialog>

            <BoardPageShell
                board={(
                    <Box sx={{ width: '100%', height: '100%', display: 'grid', placeItems: 'center', minWidth: 0, minHeight: 0 }}>
                        <div style={{
                            display: (view3d && Board3D) ? 'none' : 'flex',
                            width: '100%', height: '100%',
                            justifyContent: 'center', alignItems: 'center'
                        }}>
                            <Board
                                gameState={gameState}
                                onMove={(x, y) => isPlayer ? onMove(x, y) : {}}
                                analysisToggles={{ coords: displayToggles.coords, numbers: displayToggles.numbers }}
                            />
                        </div>
                        {view3d && Board3D && (
                            <Board3D
                                gameState={gameState}
                                onMove={(x, y) => isPlayer ? onMove(x, y) : {}}
                                analysisToggles={displayToggles}
                            />
                        )}
                        {view3d && !Board3D && <CircularProgress />}
                    </Box>
                )}
                modulePlate={(
                    <ModulePlate
                        title={t('game_room:title', '对局室')}
                        subtitle={`${gameState.players_info.B.name} vs ${gameState.players_info.W.name} · ${t('game_room:board_size', '{n} 路').replace(/\{n\}/g, String(gameState.board_size[0]))}`}
                        /* 棋盘上方那条横栏取消了。「轮到你了 / 对方回合 / 观战中」升到这里成为状态徽章 ——
                           它是这一屏此刻的状态，模块牌右侧正是放状态的地方。 */
                        status={
                            isGameOver
                                ? <Chip size="small" color="success" variant="outlined" label={t('game_room:ended', '已结束')} />
                                : !isPlayer
                                    ? <Chip size="small" variant="outlined" label={t('game_room:spectating', '观战中')} />
                                    : myTurn
                                        ? <Chip size="small" color="primary" label={t('game_room:your_turn', '轮到你了')} />
                                        : <Chip size="small" variant="outlined" label={t('game_room:opponents_turn', '对手回合')} />
                        }
                        backTo="/galaxy/play/human"
                        backLabel={t('game_room:lobby_short', '大厅')}
                    />
                )}
                railBody={(
                    <RightSidebarPanel
                        gameState={gameState}
                        analysisToggles={{ ownership: false, hints: false, score: false, policy: false, ...displayToggles }}
                        onToggleChange={handleToggleChange}
                        onNavigate={onNavigate}
                        onAction={isPlayer ? handleActionWrapper : () => {}}
                        /* 人人对弈没有引擎 —— 分析类道具一律锁死。这与「这局算不算段位」是两件事：
                           以前这里无条件传 isRated={true}，于是一局**自由**对弈也挂着升降级横幅。 */
                        analysisLocked
                        isRated={isRankedGameType(gameState.game_type)}
                        isSpectator={!isPlayer}
                        spectatorCount={spectatorCount}
                        resultAlert={gameState.end_result
                            ? <Alert severity="success" variant="outlined">{translateResult(gameState.end_result, t, gameState.ruleset)}</Alert>
                            : undefined}
                        onLeave={handleLeave}
                        embedded
                    />
                )}
                actions={<RightSidebarActions onAction={isPlayer ? handleActionWrapper : () => {}} isGameOver={isGameOver} />}
            />
        </Box>
    );
};

export default GameRoomPage;
