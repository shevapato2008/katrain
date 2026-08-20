import { useState, useEffect, useCallback, useRef } from 'react';
import { API, type GameState, type PhysicalEngineErrorState } from '../api';

interface GameEndData {
    reason: 'resign' | 'forfeit' | 'timeout' | 'count' | 'normal';
    winner_id?: number;
    result?: string;
    leaver_id?: number;
}

interface CountRequestData {
    requester_id: number;
    requester_name: string;
}

interface UseGameSessionOptions {
    token?: string;  // Auth token for multiplayer games
    onGameEnd?: (data: GameEndData) => void;  // Callback when game ends
    onCountRequest?: (data: CountRequestData) => void;  // Callback for count request (HvH)
    onCountRejected?: () => void;  // Callback when count request is rejected
    onCountTimeout?: () => void;  // Callback when count request times out
}

export const useGameSession = (options: UseGameSessionOptions = {}) => {
    const { token, onGameEnd, onCountRequest, onCountRejected, onCountTimeout } = options;
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [error, setError] = useState<string | null>(null);
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
    const audioCache = useRef<Record<string, HTMLAudioElement>>({});
    const lastSoundRef = useRef<{name: string, time: number} | null>(null);

    const playSound = useCallback((sound: string) => {
        if (typeof localStorage !== 'undefined' && localStorage.getItem('kioskPlaySound') === '0') return;
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

    useEffect(() => {
        if (sessionId) {
            const connect = async () => {
                try {
                    const data = await API.getState(sessionId, token);
                    setGameState(data.state);

                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${sessionId}`);
                    wsRef.current = ws;
                    
                    ws.onmessage = (event) => {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'game_update') {
                            setGameState(msg.state);
                        } else if (msg.type === 'spectator_count') {
                            // Lightweight update for spectator count only (doesn't reset timers)
                            setGameState(prev => prev ? { ...prev, sockets_count: msg.count } : prev);
                        } else if (msg.type === 'sound') {
                            playSound(msg.data.sound);
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
                } catch (err) {
                    console.error("Failed to connect", err);
                    setError("Failed to connect to game");
                }
            };
            connect();
            return () => {
                wsRef.current?.close();
                wsRef.current = null;
            };
        }
    }, [sessionId, playSound]);

    const onMove = useCallback(async (x: number, y: number) => {
        if (!sessionId) return;
        await API.playMove(sessionId, { x, y }, token);
    }, [sessionId, token]);

    const onNavigate = useCallback(async (nodeId: number) => {
        if (!sessionId) return;
        await API.navigate(sessionId, nodeId, token);
    }, [sessionId, token]);

    const handleAction = useCallback(async (action: string) => {
        if (!sessionId) return;
        try {
            let result: any;
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
            else if (action === 'resign') result = await API.resign(sessionId, token);
            else if (action === 'timeout') result = await API.timeout(sessionId, token);
            else if (action === 'rotate') await API.rotate(sessionId);
            else if (action === 'mistake-prev') result = await API.findMistake(sessionId, 'undo');
            else if (action === 'mistake-next') result = await API.findMistake(sessionId, 'redo');
            // Apply state from the HTTP response immediately (a WebSocket broadcast may
            // also arrive, but this ensures the acting client updates without waiting)
            if (result?.state) {
                setGameState(result.state);
            }
        } catch (e) {
            console.error(e);
            const message = e instanceof Error ? e.message : 'Game action failed';
            setError(message);
            throw e;
        }
    }, [sessionId, token]);

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
        sessionId, setSessionId, gameState, setGameState, error, onMove, onNavigate, handleAction,
        initNewSession, lastLog, chatMessages, sendChat, gameEndData, physicalReminder,
        physicalEngineError, clearPhysicalEngineError, awaitingRemovalReminder, wsRef,
    };
};
