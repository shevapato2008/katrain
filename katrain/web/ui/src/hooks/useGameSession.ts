import { useState, useEffect, useLayoutEffect, useCallback, useRef } from 'react';
import { API, type EndGameResponse, type GameState, type PhysicalEngineErrorState } from '../api';
import { websocketUrl, WS_POLICY_VIOLATION, WS_SESSION_GONE_REASON, SESSION_GONE_MESSAGE } from '../utils/websocketUrl';
import { readAudioPref } from '../utils/audioPrefs';
import { requestFailureKind } from '../utils/requestFailure';

interface GameEndData {
    reason: 'resign' | 'forfeit' | 'timeout' | 'count' | 'normal';
    winner_id?: number;
    result?: string;
    leaver_id?: number;
}

function isSessionGone(error: unknown): boolean {
    return requestFailureKind(error) === 'not_found';
}

interface CountRequestData {
    requester_id: number;
    requester_name: string;
}

interface UseGameSessionOptions {
    token?: string;  // Auth token for multiplayer games
    deferMoveSoundUntilPaint?: boolean;  // Kiosk: wait for the visible canvas to acknowledge the node
    onGameEnd?: (data: GameEndData) => void;  // Callback when game ends
    onCountRequest?: (data: CountRequestData) => void;  // Callback for count request (HvH)
    onCountRejected?: () => void;  // Callback when count request is rejected
    onCountTimeout?: () => void;  // Callback when count request times out
}

type QueuedSound = { sound: string; afterNodeId: number };

export const useGameSession = (options: UseGameSessionOptions = {}) => {
    const { token, deferMoveSoundUntilPaint = false, onGameEnd, onCountRequest, onCountRejected, onCountTimeout } = options;
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [error, setError] = useState<string | null>(null);
    // 断线是持续状态，与一次性操作失败分开；保留 error 的既有文案供其它调用方使用。
    const [connectionLost, setConnectionLost] = useState<'rejected' | 'dropped' | 'gone' | null>(null);
    const [lastLog, setLastLog] = useState<string | null>(null);
    // wire 契约 `shapes.Chat`:身份两项由服务端填,字段叫 `from_name` **不叫 `sender`**。
    const [chatMessages, setChatMessages] = useState<{from_id: number, from_name: string, text: string}[]>([]);
    const [gameEndData, setGameEndData] = useState<GameEndData | null>(null);
    const [physicalReminder, setPhysicalReminder] = useState<{
        kind: 'reminder' | 'escalation';
        to_place: number[][];
        to_remove: number[][];
    } | null>(null);
    // Task 9: bounded-retry engine-tunnel failure (Golaxy 隧道). Set on `physical_engine_error`,
    // cleared to null on the backend's `physical_engine_error_resolved` (awaiting-removal stability
    // gate satisfied) — EngineMoveErrorDialog also has a local `clearPhysicalEngineError` escape
    // hatch (retry ok:true / stale-token 409) since those two outcomes have no matching broadcast.
    const [physicalEngineError, setPhysicalEngineError] = useState<PhysicalEngineErrorState | null>(null);
    // Task 8's awaiting-removal timeout re-prompt (`_tick_awaiting_removal`'s reminder broadcast).
    // A fresh object on every occurrence (like physicalReminder) so a dialog can key an effect off
    // it to re-emphasize the waiting UI without needing a dedicated ack/clear round-trip.
    const [awaitingRemovalReminder, setAwaitingRemovalReminder] = useState<{ row: number; col: number } | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    /* 「这一局已经有结果了」。要 ref 是因为 `ws.onclose` 的闭包建于**建连那一刻**,直接读
       `gameState` 读到的是那一刻的值。来源只取 state 里的 `end_result` —— 它**会**随下一局
       自己回到 false(新局的 state 不带 end_result),不需要谁记得去清。
       不用 `gameEndData`:那个 state 没有任何清除者(`setGameEndData` 全仓只有 `game_end`
       那一处调用),一旦为真就再也回不去。而 galaxy 的 GameRoomPage 会在**同一个挂载的
       hook** 上换 sessionId,那种「页内再来一局」会让下一局真正的回收被这里吞掉。 */
    const gameEndedRef = useRef(false);
    const audioCache = useRef<Record<string, HTMLAudioElement>>({});
    const lastSoundRef = useRef<{name: string, time: number} | null>(null);
    const soundQueueRef = useRef<QueuedSound[]>([]);
    const committedNodeRef = useRef<number | null>(null);
    const paintedNodeRef = useRef<number | null>(null);
    const committedGameRef = useRef<string | null>(null);
    const soundRafRef = useRef<number[]>([]);

    const playSound = useCallback((sound: string) => {
        // 提示音只留一把:设置屏「落子音效」、屏 04「落子提示音」、这里读的都是 audioPrefs 的 sfx
        // (v2 §4.1)。galaxy 也走这个 hook —— 它从不写这把键,readAudioPref 缺键当开,行为不变。
        if (!readAudioPref('sfx')) return;
        const now = Date.now();
        // Prevent duplicate rapid sounds
        if (lastSoundRef.current && lastSoundRef.current.name === sound && now - lastSoundRef.current.time < 300) {
            return;
        }
        lastSoundRef.current = { name: sound, time: now };

        if (!audioCache.current[sound]) {
            audioCache.current[sound] = new Audio(`/assets/sounds/${sound}.wav`);
        }
        const audio = audioCache.current[sound];
        audio.currentTime = 0;
        audio.play().catch(e => console.warn("Failed to play sound", e));
    }, []);

    const clearQueuedSounds = useCallback(() => {
        soundQueueRef.current = [];
        paintedNodeRef.current = null;
        soundRafRef.current.forEach(id => cancelAnimationFrame(id));
        soundRafRef.current = [];
    }, []);

    const flushQueuedSounds = useCallback((): void => {
        if (soundRafRef.current.length > 0) return;
        const matchingIndex = soundQueueRef.current.findIndex(
            queued => queued.afterNodeId === committedNodeRef.current
                && (!deferMoveSoundUntilPaint || queued.afterNodeId === paintedNodeRef.current),
        );
        if (matchingIndex < 0) return;
        if (matchingIndex > 0) {
            soundQueueRef.current.splice(0, matchingIndex);
        }
        const next = soundQueueRef.current[0];
        if (!next) return;

        const finishPlayback = () => {
            if (soundQueueRef.current[0] === next) {
                soundQueueRef.current.shift();
                if (next.afterNodeId === committedNodeRef.current
                    && (!deferMoveSoundUntilPaint || next.afterNodeId === paintedNodeRef.current)) {
                    playSound(next.sound);
                }
            }
            flushQueuedSounds();
        };

        const firstRaf = requestAnimationFrame(() => {
            soundRafRef.current = soundRafRef.current.filter(id => id !== firstRaf);
            // Board acknowledges drawImage completion, not screen presentation.
            // RAF runs before paint, so even that acknowledgement needs two frames:
            // the first gives the browser a chance to present the new stone.
            const secondRaf = requestAnimationFrame(() => {
                soundRafRef.current = soundRafRef.current.filter(id => id !== secondRaf);
                finishPlayback();
            });
            soundRafRef.current.push(secondRaf);
        });
        soundRafRef.current.push(firstRaf);
    }, [deferMoveSoundUntilPaint, playSound]);

    const acknowledgePaintedNode = useCallback((nodeId: number) => {
        if (nodeId !== committedNodeRef.current) return;
        paintedNodeRef.current = nodeId;
        flushQueuedSounds();
    }, [flushQueuedSounds]);

    useLayoutEffect(() => {
        const committedGame = gameState?.game_id ?? null;
        if (committedGameRef.current !== null && committedGameRef.current !== committedGame) {
            clearQueuedSounds();
        }
        committedGameRef.current = committedGame;
        const committedNode = gameState?.current_node_id ?? null;
        if (committedNodeRef.current !== committedNode) {
            paintedNodeRef.current = null;
        }
        committedNodeRef.current = committedNode;
        flushQueuedSounds();
    }, [gameState?.game_id, gameState?.current_node_id, clearQueuedSounds, flushQueuedSounds]);

    useEffect(() => clearQueuedSounds, [clearQueuedSounds]);

    useEffect(() => {
        gameEndedRef.current = Boolean(gameState?.end_result);
    }, [gameState]);

    useEffect(() => {
        if (sessionId) {
            let disposed = false;
            let ownedWs: WebSocket | null = null;
            const connect = async () => {
                try {
                    const data = await API.getState(sessionId, token);
                    if (disposed) return;
                    setGameState(data.state);

                    /* token 必须带上 —— 服务端 `/ws/{session_id}` 是要鉴权的，而这里
                       在此之前一个凭据都不发（`/ws/lobby` 一直是带的）。详见
                       utils/websocketUrl.ts 里记的那次回归。 */
                    if (disposed) return;
                    const ws = new WebSocket(websocketUrl(`/ws/${sessionId}`, token));
                    ownedWs = ws;
                    wsRef.current = ws;
                    ws.onopen = () => { if (wsRef.current === ws) setConnectionLost(null); };
                    
                    ws.onmessage = (event) => {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'game_update') {
                            setGameState(msg.state);
                        } else if (msg.type === 'spectator_count') {
                            // Lightweight update for spectator count only (doesn't reset timers)
                            setGameState(prev => prev ? { ...prev, sockets_count: msg.count } : prev);
                        } else if (msg.type === 'sound') {
                            if (typeof msg.data.after_node_id === 'number') {
                                soundQueueRef.current.push({
                                    sound: msg.data.sound,
                                    afterNodeId: msg.data.after_node_id,
                                });
                                flushQueuedSounds();
                            } else {
                                playSound(msg.data.sound);
                            }
                        } else if (msg.type === 'log') {
                            setLastLog(msg.data.message);
                        } else if (msg.type === 'chat') {
                            // 契约把 chat 定成**扁平帧**(不套 data),与三家共享侧逐字一致。
                            setChatMessages(prev => [...prev, { from_id: msg.from_id, from_name: msg.from_name, text: msg.text }]);
                        } else if (msg.type === 'game_end') {
                            setGameEndData(msg.data);
                            if (onGameEnd) {
                                onGameEnd(msg.data);
                            }
                        } else if (msg.type === 'count_request') {
                            if (onCountRequest) {
                                onCountRequest(msg.data);
                            }
                        } else if (msg.type === 'count_rejected') {
                            if (onCountRejected) {
                                onCountRejected();
                            }
                        } else if (msg.type === 'count_timeout') {
                            if (onCountTimeout) {
                                onCountTimeout();
                            }
                        } else if (msg.type === 'physical_reminder') {
                            setPhysicalReminder(msg.data);
                        } else if (msg.type === 'physical_engine_error') {
                            // Top-level fields (NOT nested under `data`) — matches
                            // _apply_engine_recovery_outcome's broadcast shape.
                            setPhysicalEngineError({
                                col: msg.col,
                                row: msg.row,
                                attempts: msg.attempts,
                                detail: msg.detail,
                                recovery_token: msg.recovery_token,
                            });
                        } else if (msg.type === 'physical_engine_error_resolved') {
                            setPhysicalEngineError(null);
                        } else if (msg.type === 'physical_awaiting_removal_reminder') {
                            setAwaitingRemovalReminder(msg.data);
                        }
                    };

                    /* 这条通道断了必须**说出来**。在此之前它一个回调都没有：服务端
                       `close(1008, "Invalid token")` 在浏览器里悄无声息，于是
                       AI 的每一手都推不过来、棋盘停在人类那一手，用户只看到
                       「点了没反应」。对局状态全靠这条推送，它断 = 页面在撒谎。 */
                    ws.onclose = (event) => {
                        if (wsRef.current !== ws) return;  // 已被新连接替换或组件卸载
                        clearQueuedSounds();
                        if (event.code === WS_POLICY_VIOLATION && event.reason === WS_SESSION_GONE_REASON) {
                            if (gameEndedRef.current) {
                                /* 这一局已经有结果了 —— 结果不能被「这一局没了」顶掉。服务端那边
                                   有意收尾走的是正常关闭(session.py 的 SOCKET_CLOSE_SESSION_CLOSED),
                                   所以正常情况下到不了这里;这一条兜的是「终局卡还在屏上时会话被闲置
                                   回收」那一种 —— 那时候「这一局没了」是真的,但用户要看的是结果。
                                   离开判负(`/api/multiplayer/leave`)那一种**不**落进这个条件:它只广播
                                   `game_end`、不写 state 的 `end_result`。不要紧 —— 那条路同一个处理函数
                                   当场就把会话拆了,后面不会再有「闲置回收」找上这一局。 */
                                console.warn('Session reclaimed after the game had already ended');
                                return;
                            }
                            // 服务端把这局回收了。这不是凭据问题 —— 走下面那条会告诉用户
                            // 「请重新登录」,而重新登录救不了它。说错原因和印原始报错一样不算人话。
                            console.warn('Game session is gone on the server');
                            setConnectionLost('gone');
                            setError(SESSION_GONE_MESSAGE);
                        } else if (event.code === WS_POLICY_VIOLATION) {
                            // Kiosk's GamePage shows a fixed sentence for 'rejected' (raw 1008
                            // reasons aren't actionable on a 7" screen - see the comment above
                            // that Snackbar branch) and `error` below is galaxy's channel, not
                            // kiosk's. This console line is now the ONLY place the kiosk keeps
                            // the actual reason - do not delete it in a future cleanup.
                            console.error("Game WebSocket rejected:", event.reason);
                            setConnectionLost('rejected');
                            setError(`实时连接被拒绝（${event.reason || '凭据无效'}），棋盘不会自动更新，请重新登录后重试`);
                        } else if (!event.wasClean) {
                            console.warn("Game WebSocket closed:", event.code, event.reason);
                            setConnectionLost('dropped');
                            setError("实时连接已断开，棋盘不会自动更新，请刷新页面");
                        }
                    };
                } catch (err) {
                    if (disposed) return;
                    console.error("Failed to connect", err);
                    setError("Failed to connect to game");
                }
            };
            connect();
            return () => {
                disposed = true;
                clearQueuedSounds();
                if (wsRef.current === ownedWs) {
                    wsRef.current = null;  // 先清空，让上面的 onclose 认出这是我们自己关的
                }
                ownedWs?.close();
            };
        }
    }, [sessionId, token, playSound, clearQueuedSounds, flushQueuedSounds]);

    const onMove = useCallback(async (x: number, y: number) => {
        if (!sessionId) return;
        await API.playMove(sessionId, { x, y }, token);
    }, [sessionId, token]);

    const onNavigate = useCallback(async (nodeId: number) => {
        if (!sessionId) return;
        await API.navigate(sessionId, nodeId, token);
    }, [sessionId, token]);

    const handleAction = useCallback(async (action: string, opts?: { color?: 'B' | 'W' }) => {
        if (!sessionId) return;
        try {
            // 这一族端点要么回常规回执,要么回「这局没了」。写成联合类型(而不是 any)是为了
            // 让 `tsc -b` 在**这个 hook** 里也盯着收窄 —— 三条通道都汇到这里,页面那两个
            // 调用点被盯着而这里不被盯着,等于闸建在了人少的那一侧。
            let result: EndGameResponse | undefined;
            if (action === 'pass') await API.playMove(sessionId, null, token);
            else if (action === 'undo') result = await API.undo(sessionId, 'smart');
            else if (action === 'back') result = await API.undo(sessionId, 1);
            else if (action === 'back-10') result = await API.undo(sessionId, 10);
            else if (action === 'start') result = await API.undo(sessionId, 9999);
            else if (action === 'forward') result = await API.redo(sessionId, 1);
            else if (action === 'forward-10') result = await API.redo(sessionId, 10);
            else if (action === 'end') result = await API.redo(sessionId, 9999);
            else if (action === 'ai-move') await API.aiMove(sessionId);
            // Resign/timeout apply their response like undo/redo do. Both endpoints
            // already return the finished state; relying on the broadcast instead left
            // the acting client sitting in a game the server had already ended (and,
            // for 升降级对弈, never showing the settlement that follows it).
            // 本地对局(pvp_local)的认输要说**是哪一方**认输(后端不带 color 回 400);
            // 其它模式不许带(带了同样 400)⇒ 没给 color 时调用形状与原来逐字一致。
            else if (action === 'resign') result = opts?.color
                ? await API.resign(sessionId, token, opts.color)
                : await API.resign(sessionId, token);
            else if (action === 'timeout') result = await API.timeout(sessionId, token);
            else if (action === 'rotate') await API.rotate(sessionId);
            else if (action === 'mistake-prev') result = await API.findMistake(sessionId, 'undo');
            else if (action === 'mistake-next') result = await API.findMistake(sessionId, 'redo');
            // Task 2 的 200 空回执。只看 `result?.state` 会把它当成静默成功:框关掉、棋局
            // 永远不终局、页面完全不知道这局已经死了。它**不带**任何结果 —— 会话没了不等于
            // 远端认输了(真正的远端认输在 gateway.py:399-420,那条路这时根本没走到)。
            // `'status' in result` 是完整判别式:`SessionResponse` 没有 `status` 这个键。
            // **不要**写成 `&& result.status === 'session_gone'` —— 那个复合形式会让 TS
            // 在落空分支上收不窄,下面读 `result.state` 当场报错(GamePage 的 send() 记过)。
            if (result && 'status' in result) {
                setConnectionLost('gone');
                setError(SESSION_GONE_MESSAGE);
                return;
            }
            // Apply state from the HTTP response immediately (a WebSocket broadcast may
            // also arrive, but this ensures the acting client updates without waiting)
            if (result?.state) {
                setGameState(result.state);
            }
        } catch (e) {
            console.error(e);
            if (isSessionGone(e)) {
                // 同一个信号的第三条来路。**不能**把 e.message 放进 error:那正是
                // `Request failed 404: {"detail":…}` 上屏的那条路。
                setConnectionLost('gone');
                setError(SESSION_GONE_MESSAGE);
                throw e;
            }
            const message = e instanceof Error ? e.message : 'Game action failed';
            setError(message);
            throw e;
        }
    }, [sessionId, token]);

    const clearError = useCallback(() => setError(null), []);

    // 第四条通道。这局没了目前有三条发现路径(WS 1008/session_gone、handleAction 的 200
    // session_gone 回执、handleAction 的 404 catch),GamePage 里还有两处绕过 handleAction
    // 直接打 API.timeout 的调用点(自动超时判定),它们发现"没了"之后没有地方可以报。
    // 这个回调就是那个地方 —— 与前三条写的是同一对 state,调用方不需要,也不应该,
    // 自己另开一个"gone"标志。
    const reportSessionGone = useCallback(() => {
        setConnectionLost('gone');
        setError(SESSION_GONE_MESSAGE);
    }, []);

    const initNewSession = useCallback(async () => {
        const data = await API.createSession(token);
        setSessionId(data.session_id);
        return data.session_id;
    }, [token]);

    // Task 9: local escape hatch for the two engine-error-recovery outcomes that have no
    // matching WS broadcast (retry ok:true, and a stale/consumed-token 409) — the dialog
    // calls this itself rather than waiting on the server.
    const clearPhysicalEngineError = useCallback(() => setPhysicalEngineError(null), []);

    // 只发正文。发送者身份**由服务端从会话身份填**(server.py 的 chat 分支),客户端传
    // `sender` 是没有意义的 —— 它以前会被原样广播出去,于是任何人都能冒名发言。
    const sendChat = useCallback((text: string) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'chat', text }));
        }
    }, []);

    // wsRef is exposed so callers can layer additional message-type listeners on the
    // same socket (e.g. usePlatformEvents for platform_move_pending/confirmed/rejected —
    // engine-play (Golaxy 人机对弈) commit-protocol events; see kiosk GamePage's undo-
    // disable-while-pending wiring). This hook's own onmessage switch above only handles
    // the generic game-session message types and deliberately ignores platform_* ones.
    return {
        sessionId, setSessionId, gameState, setGameState, error, connectionLost, clearError, reportSessionGone, onMove, onNavigate, handleAction,
        initNewSession, lastLog, chatMessages, sendChat, gameEndData, physicalReminder,
        physicalEngineError, clearPhysicalEngineError, awaitingRemovalReminder, wsRef,
        acknowledgePaintedNode,
    };
};
