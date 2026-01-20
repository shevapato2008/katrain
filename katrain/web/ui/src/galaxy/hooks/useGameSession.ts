import { useState, useEffect, useRef } from 'react';
import { API, GameState } from '../../api';

export const useGameSession = () => {
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const initSession = async () => {
            try {
                // Check if we have a stored session or create new
                // For Research, we usually want a clean session or load a specific game
                // Let's create a new session for now
                const data = await API.createSession();
                setSessionId(data.session_id);
                setGameState(data.state);
                
                // Setup WebSocket (reused from App.tsx pattern)
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${data.session_id}`);
                
                ws.onmessage = (event) => {
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'game_update') {
                        setGameState(msg.state);
                    }
                };
                
                return () => {
                    ws.close();
                };
            } catch (err) {
                console.error("Failed to init session", err);
                setError("Failed to initialize game session");
            }
        };

        initSession();
    }, []);

    const onMove = async (x: number, y: number) => {
        if (!sessionId) return;
        await API.playMove(sessionId, { x, y });
    };

    const onNavigate = async (nodeId: number) => {
        if (!sessionId) return;
        await API.navigate(sessionId, nodeId);
    };

    // Add other actions as needed

    return { sessionId, gameState, error, onMove, onNavigate };
};
