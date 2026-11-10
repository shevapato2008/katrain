import { useMemo } from 'react';
import type { GameState } from '../../api';
import type { PositionAnalysis } from '../membership/types';
import { usePaidPosition } from './usePaidPosition';

/** Project a private receipt without mutating the shared session or its history. */
export function projectPaidPlayPosition(raw: GameState, result: PositionAnalysis['result'] | null): GameState {
  const [width, height] = raw.board_size;
  const root = result?.rootInfo;
  const letters = 'ABCDEFGHJKLMNOPQRSTUVWXYZ';
  return { ...raw,
    history: raw.history.map((node) => ({ ...node,
      score: result && node.node_id === raw.current_node_id ? root?.scoreLead ?? null : null,
      winrate: result && node.node_id === raw.current_node_id ? root?.winrate ?? null : null,
    })),
    stones: raw.stones.map(([player, coords, , moveNumber]) => [player, coords, null, moveNumber]),
    analysis: result ? { visits: root?.visits, winrate: root?.winrate, score: root?.scoreLead,
      ownership: result.ownership.length === width * height
        // KataGo starts at the top left; Board indexes y from the bottom, as var_to_grid does.
        ? Array.from({ length: height }, (_, y) => result.ownership.slice((height - 1 - y) * width, (height - y) * width)) : null,
      moves: result.moves.map((move) => ({ ...move, scoreLead: move.score_lead,
        coords: move.move.toLowerCase() === 'pass' ? null : [letters.indexOf(move.move[0]), Number(move.move.slice(1)) - 1],
        scoreLoss: root ? Math.max(0, (root.scoreLead - move.score_lead) * (raw.player_to_move === 'W' ? -1 : 1)) : undefined,
      })),
    } : { moves: [], ownership: null },
    ui_state: { ...raw.ui_state, show_hints: false, show_ownership: false, show_policy: false },
  };
}

interface Options {
  gameState: GameState | null;
  sessionId: string | undefined;
  identityKey: string | null | undefined;
  status: string;
  token?: string | null;
  isGuest?: boolean;
  engineMode?: boolean;
}

export function usePaidPlayPosition({ gameState: raw, sessionId, identityKey, status, token, isGuest, engineMode }: Options) {
  const active = !engineMode && raw?.game_type === 'free' && raw.analysis_delivered === false;
  const authenticated = status === 'authenticated' && !!identityKey && !isGuest;
  // A delivered=false frame does not identify its owner. The server still enforces participation.
  const eligible = active && authenticated && !!sessionId && raw.analysis_allowed !== false && !!raw.expected_position_key;
  const snapshotKey = JSON.stringify([sessionId, raw?.game_id, raw?.expected_position_key, raw?.current_node_id,
    raw?.current_node_index, raw?.history.map(({ node_id, move, player }) => [node_id, move, player]), raw?.stones,
    raw?.board_size, raw?.player_to_move, raw?.ruleset, raw?.komi]);
  const paid = usePaidPosition({ identityKey, status, token, snapshotKey, profile: 'normal',
    input: { session_id: sessionId, expected_position_key: raw?.expected_position_key ?? undefined }, enabled: eligible });
  const gameState = useMemo(() => !raw ? null : active ? projectPaidPlayPosition(raw, paid.result) : raw, [active, raw, paid.result]);
  return { ...paid, active, eligible, gameState,
    requiresLogin: active ? !authenticated : raw?.analysis_delivered === false,
    unavailable: (active && authenticated && !eligible) || (raw?.game_type === 'free' && raw.analysis_allowed === false),
  };
}
