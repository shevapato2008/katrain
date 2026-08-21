/**
 * useResearchSession: Research-specific session hook.
 * Extends useSessionBase with research mode features:
 * - No turn validation (free stone placement)
 * - Session lifecycle (create/destroy research sessions)
 * - Analysis toggle controls
 */
import { useCallback, useState } from 'react';
import { useSessionBase } from './useSessionBase';
import { API, apiPost, authHeaders } from '../api';
import type { GameState } from '../api';

export interface UseResearchSessionReturn {
    // Session state
    sessionId: string | null;
    gameState: GameState | null;
    error: string | null;
    isConnected: boolean;

    // Session lifecycle
    createSession: (sgf?: string, options?: { skipAnalysis?: boolean; initialMove?: number }) => Promise<string | null>;
    destroySession: () => Promise<void>;

    // Board actions (delegated to useSessionBase)
    onMove: (x: number, y: number) => Promise<void>;
    onPass: () => Promise<void>;
    onNavigate: (nodeId: number) => Promise<void>;
    handleNavAction: (action: 'start' | 'back' | 'back-10' | 'forward' | 'forward-10' | 'end') => Promise<void>;

    // Analysis toggles
    toggleHints: () => Promise<void>;
    toggleOwnership: () => Promise<void>;
    toggleMoveNumbers: () => Promise<void>;
    toggleCoordinates: () => Promise<void>;

    // Game analysis
    analyzeGame: (visits?: number) => Promise<void>;
    analysisScan: (visits?: number) => Promise<void>;
}

export function useResearchSession(): UseResearchSessionReturn {
    const [isConnected, setIsConnected] = useState(false);

    const base = useSessionBase({
        onStateUpdate: () => {
            setIsConnected(true);
        },
    });

    /* 这一串原来是四个手写 fetch，只带 Content-Type。后果不是「少个头」而是
       **会话没有主人**：POST /api/session 是 get_current_user_optional，没带凭证
       就把 session.user_id 建成 None；随后 /api/state 的 guard_session_reader
       要求 current_user.id ∈ {user_id, player_b_id, player_w_id}，于是 403，
       gameState 永远拿不到，页面卡在「正在分析棋局」进不去 L3。
       本机看不出来，是因为 127.0.0.1 上有 sb_token cookie，浏览器会自动带上，
       建会话和读状态用的是同一个身份；换成 go.sailorvoyage.top 就没这块 cookie。
       统一走 apiPost（api.ts 的 authHeaders 会兜底带上 Bearer），建会话和用会话
       就是同一个身份。 */
    const createSession = useCallback(async (sgf?: string, options?: { skipAnalysis?: boolean; initialMove?: number }): Promise<string | null> => {
        try {
            const data = await apiPost('/api/session?mode=research', {});

            // Load SGF if provided
            if (sgf) {
                await apiPost('/api/sgf/load', {
                    session_id: data.session_id,
                    sgf,
                    skip_analysis: options?.skipAnalysis ?? false,
                });

                // Navigate to the target move (SGF loads at root by default)
                const targetMove = options?.initialMove ?? 999;
                if (targetMove > 0) {
                    const redoData = await apiPost('/api/redo', { session_id: data.session_id, n_times: targetMove });
                    // Set initial gameState immediately from redo response to avoid
                    // race conditions with WS initial state or analysis callbacks
                    if (redoData.state) {
                        base.setGameState(redoData.state);
                    }
                }
            }

            // Connect WebSocket (will also fetch state, but we already have it)
            base.setSessionId(data.session_id);
            return data.session_id;
        } catch (err) {
            console.error('Failed to create research session:', err);
            return null;
        }
    }, [base]);

    const destroySession = useCallback(async () => {
        if (base.sessionId) {
            try {
                // 同样要带身份：会话归属校验认的是 current_user.id
                await fetch(`/api/session/${base.sessionId}`, { method: 'DELETE', headers: authHeaders() });
            } catch { /* ignore */ }
        }
        base.disconnect();
        setIsConnected(false);
    }, [base]);

    const toggleHints = useCallback(async () => {
        if (!base.sessionId) return;
        await API.toggleUI(base.sessionId, 'show_hints');
    }, [base.sessionId]);

    const toggleOwnership = useCallback(async () => {
        if (!base.sessionId) return;
        await API.toggleUI(base.sessionId, 'show_ownership');
    }, [base.sessionId]);

    const toggleMoveNumbers = useCallback(async () => {
        if (!base.sessionId) return;
        await API.toggleUI(base.sessionId, 'show_move_numbers');
    }, [base.sessionId]);

    const toggleCoordinates = useCallback(async () => {
        if (!base.sessionId) return;
        await API.toggleUI(base.sessionId, 'show_coordinates');
    }, [base.sessionId]);

    const analyzeGame = useCallback(async (visits?: number) => {
        if (!base.sessionId) return;
        await API.analyzeGame(base.sessionId, visits);
    }, [base.sessionId]);

    const analysisScan = useCallback(async (visits?: number) => {
        if (!base.sessionId) return;
        await API.analysisScan(base.sessionId, visits);
    }, [base.sessionId]);

    return {
        sessionId: base.sessionId,
        gameState: base.gameState,
        error: base.error,
        isConnected,
        createSession,
        destroySession,
        onMove: base.onMove,
        onPass: base.onPass,
        onNavigate: base.onNavigate,
        handleNavAction: base.handleNavAction,
        toggleHints,
        toggleOwnership,
        toggleMoveNumbers,
        toggleCoordinates,
        analyzeGame,
        analysisScan,
    };
}
