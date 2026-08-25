/**
 * useSessionBase: Common WebSocket connection, GameState management, and navigation
 * shared between useGameSession and useResearchSession.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { API, type GameState } from '../api';
import { websocketUrl, WS_POLICY_VIOLATION } from '../utils/websocketUrl';

export interface UseSessionBaseOptions {
    onStateUpdate?: (state: GameState) => void;
    /** Auth token. /api/state requires an authenticated user; without this the initial
     *  connect 401s on any host that is not the 127.0.0.1 loopback (see API.getState). */
    token?: string;
}

export interface UseSessionBaseReturn {
    sessionId: string | null;
    setSessionId: (id: string | null) => void;
    gameState: GameState | null;
    setGameState: React.Dispatch<React.SetStateAction<GameState | null>>;
    error: string | null;
    wsRef: React.MutableRefObject<WebSocket | null>;

    // Navigation
    onNavigate: (nodeId: number) => Promise<void>;
    handleNavAction: (action: 'start' | 'back' | 'back-10' | 'forward' | 'forward-10' | 'end') => Promise<void>;

    // SGF
    loadSGF: (sgf: string) => Promise<void>;
    saveSGF: () => Promise<string | null>;

    // Move
    onMove: (x: number, y: number) => Promise<void>;
    onPass: () => Promise<void>;

    // Cleanup
    disconnect: () => void;
}

export function useSessionBase(options: UseSessionBaseOptions = {}): UseSessionBaseReturn {
    const { onStateUpdate, token } = options;
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [error, setError] = useState<string | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const audioCache = useRef<Record<string, HTMLAudioElement>>({});

    const playSound = useCallback((sound: string) => {
        if (!audioCache.current[sound]) {
            audioCache.current[sound] = new Audio(`/assets/sounds/${sound}.wav`);
        }
        const audio = audioCache.current[sound];
        audio.currentTime = 0;
        audio.play().catch(() => {});
    }, []);

    // WebSocket connection
    useEffect(() => {
        if (!sessionId) return;

        const connect = async () => {
            try {
                const data = await API.getState(sessionId, token);
                setGameState(data.state);
                onStateUpdate?.(data.state);

                /* 同 useGameSession：`/ws/{session_id}` 要鉴权，凭据只能走 query
                   （浏览器的 WebSocket 不能自定义请求头）。见 utils/websocketUrl.ts。 */
                const ws = new WebSocket(websocketUrl(`/ws/${sessionId}`, token));
                wsRef.current = ws;

                ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'game_update') {
                        setGameState(msg.state);
                        onStateUpdate?.(msg.state);
                    } else if (msg.type === 'spectator_count') {
                        setGameState(prev => prev ? { ...prev, sockets_count: msg.count } : prev);
                    } else if (msg.type === 'sound') {
                        playSound(msg.data.sound);
                    }
                };
                /* 断了要说出来 —— 静默的 1008 正是这次三周无人察觉的原因。 */
                ws.onclose = (event) => {
                    if (wsRef.current !== ws) return;  // 自己关的
                    if (event.code === WS_POLICY_VIOLATION) {
                        console.error('Session WebSocket rejected:', event.reason);
                        setError(`实时连接被拒绝（${event.reason || '凭据无效'}），棋盘不会自动更新，请重新登录后重试`);
                    } else if (!event.wasClean) {
                        console.warn('Session WebSocket closed:', event.code, event.reason);
                        setError('实时连接已断开，棋盘不会自动更新，请刷新页面');
                    }
                };
            } catch (err) {
                console.error('Failed to connect session', err);
                setError('Failed to connect to session');
            }
        };

        connect();

        return () => {
            const ws = wsRef.current;
            wsRef.current = null;
            ws?.close();
        };
    }, [sessionId, token, playSound]);

    const onMove = useCallback(async (x: number, y: number) => {
        if (!sessionId) return;
        await API.playMove(sessionId, { x, y });
    }, [sessionId]);

    const onPass = useCallback(async () => {
        if (!sessionId) return;
        await API.playMove(sessionId, null);
    }, [sessionId]);

    const onNavigate = useCallback(async (nodeId: number) => {
        if (!sessionId) return;
        await API.navigate(sessionId, nodeId);
    }, [sessionId]);

    const handleNavAction = useCallback(async (action: 'start' | 'back' | 'back-10' | 'forward' | 'forward-10' | 'end') => {
        if (!sessionId) return;
        try {
            let result: any;
            if (action === 'back') result = await API.undo(sessionId, 1);
            else if (action === 'back-10') result = await API.undo(sessionId, 10);
            else if (action === 'start') result = await API.undo(sessionId, 9999);
            else if (action === 'forward') result = await API.redo(sessionId, 1);
            else if (action === 'forward-10') result = await API.redo(sessionId, 10);
            else if (action === 'end') result = await API.redo(sessionId, 9999);
            if (result?.state) {
                setGameState(result.state);
            }
        } catch (e) {
            console.error('Navigation error:', e);
        }
    }, [sessionId]);

    const loadSGF = useCallback(async (sgf: string) => {
        if (!sessionId) return;
        const result = await API.loadSGF(sessionId, sgf);
        if (result?.state) setGameState(result.state);
    }, [sessionId]);

    const saveSGF = useCallback(async (): Promise<string | null> => {
        if (!sessionId) return null;
        const result = await API.saveSGF(sessionId);
        return result?.sgf ?? null;
    }, [sessionId]);

    const disconnect = useCallback(() => {
        wsRef.current?.close();
        wsRef.current = null;
        setSessionId(null);
        setGameState(null);
    }, []);

    return {
        sessionId, setSessionId, gameState, setGameState, error, wsRef,
        onNavigate, handleNavAction, loadSGF, saveSGF,
        onMove, onPass, disconnect,
    };
}
