import type { AiLadderCatalogEntry, AiLadderStatus } from '../types';

export type AiLadderDemoState = 'placement' | 'placed' | 'pending' | 'unavailable' | 'loading' | 'error';

const placementOpponent: AiLadderCatalogEntry = {
  rung: 17,
  rank_name: '4级',
  certification_status: 'certified',
  availability: 'available',
  route: 'server',
};

const placedRung: AiLadderCatalogEntry = {
  rung: 30,
  rank_name: '5段',
  certification_status: 'certified',
  availability: 'available',
  route: 'server',
};

// Remove when the authoritative status API replaces this visual fixture.
export const AI_LADDER_GALAXY_DEMO: Record<AiLadderDemoState, AiLadderStatus> = {
  placement: {
    view_state: 'ready',
    placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
    current_opponent: placementOpponent,
    recent_ranked_results: ['win', 'loss', 'win'],
    net_score: 0,
    pending_settlement: false,
  },
  placed: {
    view_state: 'ready',
    placement_state: { phase: 'placed', rung: placedRung },
    current_opponent: null,
    recent_ranked_results: ['win', 'win', 'loss', 'win', 'win'],
    net_score: 2,
    pending_settlement: false,
  },
  pending: {
    view_state: 'ready',
    placement_state: { phase: 'placed', rung: placedRung },
    current_opponent: null,
    recent_ranked_results: ['loss', 'win', 'win', 'loss', 'win'],
    net_score: 1,
    pending_settlement: true,
  },
  unavailable: {
    view_state: 'ready',
    placement_state: { phase: 'placement', completed_games: 3, total_games: 5 },
    current_opponent: {
      ...placementOpponent,
      certification_status: 'provisional',
      availability: 'unavailable',
    },
    recent_ranked_results: ['win', 'loss', 'win'],
    net_score: 0,
    pending_settlement: false,
  },
  loading: { view_state: 'loading' },
  error: { view_state: 'error' },
};

export const getAiLadderDemoStatus = (state: string | null): AiLadderStatus | null => {
  if (!state || !Object.prototype.hasOwnProperty.call(AI_LADDER_GALAXY_DEMO, state)) return null;
  return AI_LADDER_GALAXY_DEMO[state as AiLadderDemoState];
};
