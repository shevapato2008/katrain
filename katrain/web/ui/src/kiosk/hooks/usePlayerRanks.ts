import { useCallback, useEffect, useState } from 'react';
import type { GameState } from '../../api';
import { getAiLadderStatus } from '../../features/aiLadder/api';
import { accountRank, knownRank, type PlayerRanks } from '../utils/playerRank';

interface Options {
  sessionId?: string;
  gameState: GameState | null | undefined;
  user: { id: number; uuid?: string } | null;
  token: string | null;
  isAuthenticated: boolean;
  isGuest?: boolean;
  engineMode?: boolean;
  lobbyRoom?: boolean;
  /** Only an authoritative settlement change, never a move/node identifier. */
  settlement?: string;
}

/** Two read-only grade sources, bounded and scoped to the current account and game. */
export function usePlayerRanks({ sessionId, gameState: gs, user, token, isAuthenticated, isGuest, engineMode, lobbyRoom = false, settlement = '' }: Options): PlayerRanks {
  const realAccount = isAuthenticated && !isGuest && !!user && Number.isSafeInteger(user.id) && user.id > 0;
  const lobby = realAccount && (lobbyRoom || gs?.game_type === 'pvp_lobby');
  const owner = gs?.rank_owner;
  const ownColor = realAccount && !lobby && !engineMode && ['free', 'ranked', 'rated', 'ai_ladder_ranked'].includes(gs?.game_type ?? 'free')
    && !gs?.platform_engine_color && !gs?.platform_my_color && owner?.user_id === user?.id && (owner?.color === 'B' || owner?.color === 'W') ? owner.color : null;
  const scope = sessionId && gs?.game_id && (lobby || ownColor)
    ? JSON.stringify([user?.id, user?.uuid, token, sessionId, gs.game_id, lobby ? 'lobby' : ownColor]) : null;
  const [result, setResult] = useState<{ scope: string | null; ranks: PlayerRanks }>({ scope, ranks: {} });
  // Retire data on the render that changes identity/room, including a return to
  // a previously visited scope while the replacement request is still pending.
  if (result.scope !== scope) setResult({ scope, ranks: {} });
  const load = useCallback(async (signal: AbortSignal): Promise<PlayerRanks> => {
    if (lobby) {
      const response = await fetch('/api/v1/games/active/multiplayer', {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined, credentials: 'same-origin', signal,
      });
      if (!response.ok) throw new Error('Player ranks unavailable');
      const rows: unknown = await response.json();
      const matches = Array.isArray(rows) ? rows.filter(row => row && row.session_id === sessionId) : [];
      // Ambiguous/missing rooms are unknown; never match seats by display name.
      if (matches.length !== 1) return {};
      return { B: knownRank(matches[0].player_b_rank_label), W: knownRank(matches[0].player_w_rank_label) };
    }
    return ownColor ? { [ownColor]: accountRank(await getAiLadderStatus(token ?? undefined, signal)) } : {};
  }, [lobby, ownColor, sessionId, token]);

  useEffect(() => {
    if (!scope) return;
    let disposed = false;
    let controller: AbortController | null = null;
    let poll: ReturnType<typeof setTimeout> | undefined;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    const visible = () => document.visibilityState !== 'hidden';
    const cancel = () => { clearTimeout(poll); clearTimeout(deadline); controller?.abort(); controller = null; };
    const refresh = async () => {
      if (disposed || !visible() || controller) return;
      const request = new AbortController(); controller = request;
      try {
        const timeout = new Promise<never>((_, reject) => {
          deadline = setTimeout(() => { request.abort(); reject(new Error('Player ranks timed out')); }, 8000);
        });
        const ranks = await Promise.race([load(request.signal), timeout]);
        if (!disposed && !request.signal.aborted) setResult({ scope, ranks });
      } catch {
        if (!disposed && controller === request) setResult({ scope, ranks: {} });
      } finally {
        if (controller === request) {
          clearTimeout(deadline); controller = null;
          if (!disposed && visible()) poll = setTimeout(() => { void refresh(); }, 30000);
        }
      }
    };
    const visibility = () => { cancel(); if (visible()) void refresh(); };
    document.addEventListener('visibilitychange', visibility);
    void refresh();
    return () => { disposed = true; cancel(); document.removeEventListener('visibilitychange', visibility); };
  }, [scope, load, settlement]);
  // The render itself checks scope, before the next effect cleanup can run.
  return scope && result.scope === scope ? result.ranks : {};
}
