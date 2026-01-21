import { useState, useEffect, useCallback, useRef } from 'react';
import { API, type GameState } from '../../api';

export const useGameSession = () => {
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [gameState, setGameState] = useState<GameState | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [lastLog, setLastLog] = useState<string | null>(null);
    const [chatMessages, setChatMessages] = useState<{sender: string, text: string, time: number}[]>([]);

    const wsRef = useRef<WebSocket | null>(null);
    const audioCache = useRef<Record<string, HTMLAudioElement>>({});
    const lastSoundRef = useRef<{name: string, time: number} | null>(null);

    const playSound = useCallback((sound: string) => {
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
                    const data = await API.getState(sessionId);
                    setGameState(data.state);

                    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/${sessionId}`);
                    wsRef.current = ws;
                    
                    ws.onmessage = (event) => {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'game_update') {
                            setGameState(msg.state);
                        } else if (msg.type === 'sound') {
                            playSound(msg.data.sound);
                        } else if (msg.type === 'log') {
                            setLastLog(msg.data.message);
                        } else if (msg.type === 'chat') {
                            setChatMessages(prev => [...prev, msg.data]);
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
        await API.playMove(sessionId, { x, y });
    }, [sessionId]);

    const onNavigate = useCallback(async (nodeId: number) => {
        if (!sessionId) return;
        await API.navigate(sessionId, nodeId);
    }, [sessionId]);

    const handleAction = useCallback(async (action: string) => {
        if (!sessionId) return;
        try {
            if (action === 'pass') await API.playMove(sessionId, null);
            else if (action === 'undo') await API.undo(sessionId, 'smart');
            else if (action === 'back') await API.undo(sessionId, 1);
            else if (action === 'back-10') await API.undo(sessionId, 10);
            else if (action === 'start') await API.undo(sessionId, 9999);
            else if (action === 'forward') await API.redo(sessionId, 1);
            else if (action === 'forward-10') await API.redo(sessionId, 10);
            else if (action === 'end') await API.redo(sessionId, 9999);
            else if (action === 'ai-move') await API.aiMove(sessionId);
            else if (action === 'resign') await API.resign(sessionId);
            else if (action === 'rotate') await API.rotate(sessionId);
            else if (action === 'mistake-prev') await API.findMistake(sessionId, 'undo');
            else if (action === 'mistake-next') await API.findMistake(sessionId, 'redo');
        } catch (e) {
            console.error(e);
        }
    }, [sessionId]);

    const initNewSession = useCallback(async () => {
        const data = await API.createSession();
        setSessionId(data.session_id);
        return data.session_id;
    }, []);

    const sendChat = useCallback((text: string, sender: string) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({
                type: 'chat',
                data: { text, sender, time: Date.now() }
            }));
        }
    }, []);

    return { sessionId, setSessionId, gameState, error, onMove, onNavigate, handleAction, initNewSession, lastLog, chatMessages, sendChat };
};
