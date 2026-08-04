/**
 * TEMPORARY FIXTURE — 41-tier rated-play vertical slice S1, step 2.
 *
 * Stands in for `GET /api/ladder/me` so the rated setup page can be built and
 * visually confirmed before the endpoint exists.
 *
 * DELETION CONDITION (hard):
 *   Delete this file, and the `LADDER_ME_FIXTURE` import in
 *   `galaxy/pages/AiSetupPage.tsx`, the moment `GET /api/ladder/me` is wired in
 *   (S1 step 6, front/back integration). The slice is NOT complete while this
 *   file exists. It must never be reachable from a production build.
 *
 * Switch `ACTIVE` to pick which state the page renders while iterating.
 */
import type { LadderMe } from '../../../api';

const PLACED: LadderMe = {
    rung: 24,
    rank_name: '3段',
    rung_above: { rung: 25, rank_name: '准4段' },
    rung_below: { rung: 23, rank_name: '准3段' },
    net_wins: 1,
    threshold: 3,
    placement: null,
    recent: [
        { won: true, opponent_rung: 24, opponent_rank_name: '3段' },
        { won: false, opponent_rung: 24, opponent_rank_name: '3段' },
        { won: true, opponent_rung: 24, opponent_rank_name: '3段' },
        { won: true, opponent_rung: 24, opponent_rank_name: '3段' },
        { won: false, opponent_rung: 24, opponent_rank_name: '3段' },
    ],
    next_opponent: {
        rung: 24, rank_name: '3段',
        certification_status: 'certified', availability: 'available', route: 'server',
    },
    playable: true,
    blocked_reason: null,
};

const PLACEMENT: LadderMe = {
    rung: null,
    rank_name: null,
    rung_above: null,
    rung_below: null,
    net_wins: 0,
    threshold: 3,
    placement: { games_done: 2, games_total: 5, lo: 17, hi: 32 },
    recent: [],
    next_opponent: {
        rung: 24, rank_name: '准5段',
        certification_status: 'certified', availability: 'available', route: 'server',
    },
    playable: true,
    blocked_reason: null,
};

// What production looks like until _CERTIFIED_RUNGS stops being an empty set.
const UNCERTIFIED: LadderMe = {
    ...PLACED,
    next_opponent: { ...PLACED.next_opponent, certification_status: 'provisional', availability: 'unavailable' },
    playable: false,
    blocked_reason: 'not_certified',
};

export const LADDER_ME_FIXTURES = { PLACED, PLACEMENT, UNCERTIFIED };

const ACTIVE: keyof typeof LADDER_ME_FIXTURES = 'PLACED';

export const LADDER_ME_FIXTURE = LADDER_ME_FIXTURES[ACTIVE];
