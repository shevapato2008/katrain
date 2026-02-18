/**
 * useResearchSession: Research-specific session hook.
 * Extends useSessionBase with research mode features:
 * - No turn validation (free stone placement)
 * - Session lifecycle (create/destroy research sessions)
 * - Analysis toggle controls
 */
import { useCallback, useState } from 'react';
import { useSessionBase } from '../../hooks/useSessionBase';
import { API } from '../../api';
import type { GameState } from '../../api';

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

    const createSession = useCallback(async (sgf?: string, options?: { skipAnalysis?: boolean; initialMove?: number }): Promise<string | null> => {
        try {
            const response = await fetch('/api/session?mode=research', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            if (!response.ok) throw new Error('Failed to create research session');
            const data = await response.json();

            // Load SGF if provided
            if (sgf) {
                await fetch('/api/sgf/load', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        session_id: data.session_id,
                        sgf,
                        skip_analysis: options?.skipAnalysis ?? false,
                    }),
                });

                // Navigate to the target move (SGF loads at root by default)
                const targetMove = options?.initialMove ?? 999;
                if (targetMove > 0) {
                    const redoResp = await fetch('/api/redo', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ session_id: data.session_id, n_times: targetMove }),
                    });
                    const redoData = await redoResp.json();
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
                await fetch(`/api/session/${base.sessionId}`, { method: 'DELETE' });
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
