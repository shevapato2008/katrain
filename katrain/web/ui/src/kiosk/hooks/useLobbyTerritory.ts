import { useEffect, useRef, useState } from 'react';
import { API, type LobbyTerritoryResult } from '../../api';
import type { EngineOverlay } from '../../components/Board';

type Phase = 'idle' | 'loading' | 'result' | 'error';
interface Scope {
  sessionId?: string;
  gameId?: string;
  nodeId?: number;
  moveCount: number;
  boardSize?: [number, number];
  enabled: boolean;
  token?: string;
}
interface View { key: string; phase: Phase; result?: LobbyTerritoryResult; visible?: boolean }

/** Private, click-only reference; never writes analysis back to the shared game state. */
export function useLobbyTerritory(scope: Scope) {
  const { sessionId, gameId, nodeId, moveCount, boardSize, enabled, token } = scope;
  const key = JSON.stringify([sessionId, gameId, nodeId, moveCount, boardSize, enabled]);
  const current = useRef({ key, generation: 0 });
  if (current.current.key !== key) current.current = { key, generation: current.current.generation + 1 };
  const generation = current.current.generation;
  const viewKey = `${generation}:${key}`;
  const [view, setView] = useState<View>({ key: viewKey, phase: 'idle' });
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const phase: Phase = enabled && view.key === viewKey ? view.phase : 'idle';
  const result = phase === 'result' ? view.result : undefined;
  const visible = !!result && !!view.visible;
  const request = async () => {
    if (!enabled || !sessionId || !gameId || nodeId == null || !boardSize || inFlight.current) return;
    if (result) { setView({ ...view, visible: !visible }); return; }
    const requestedGeneration = current.current.generation;
    const stillCurrent = () => mounted.current && current.current.generation === requestedGeneration;
    inFlight.current = true;
    setPending(true);
    setView({ key: viewKey, phase: 'loading' });
    try {
      const response = await API.lobbyTerritory(sessionId, token);
      if (!stillCurrent()) return;
      if (response.stale === true || response.session_id !== sessionId || response.game_id !== gameId
        || response.current_node_id !== nodeId || response.move_count !== moveCount) {
        setView({ key: viewKey, phase: 'idle' });
        return;
      }
      const [width, height] = boardSize;
      if (response.stale !== false || !Array.isArray(response.board_size)
        || response.board_size[0] !== width || response.board_size[1] !== height
        || !Array.isArray(response.ownership) || response.ownership.length !== width * height
        || !response.ownership.every(v => Number.isFinite(v) && v >= -1 && v <= 1)
        || !Number.isFinite(response.black_area) || !Number.isFinite(response.white_area)) throw new Error('Invalid territory');
      setView({ key: viewKey, phase: 'result', result: response, visible: true });
    } catch {
      if (stillCurrent()) setView({ key: viewKey, phase: 'error' });
    } finally {
      inFlight.current = false;
      if (mounted.current) setPending(false);
    }
  };
  const overlay: EngineOverlay | null = visible && result ? {
    kind: 'area', ownership: result.ownership.map((value, index) => ({
      col: index % result.board_size[0], row: result.board_size[1] - 1 - Math.floor(index / result.board_size[0]), value,
    })),
  } : null;
  return { phase, result, overlay, visible, disabled: !enabled || pending, request };
}
