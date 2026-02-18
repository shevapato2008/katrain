// Fixed mock data — deterministic, no Math.random(). Used across all kiosk pages.

export interface KioskTimerState {
  mainTimeLeft: number;   // seconds
  byoyomiLeft: number;
  periodsLeft: number;
  isActive: boolean;
  isWarning: boolean;
  isCritical: boolean;
}

export interface KioskAnalysisPoint {
  moveIndex: number;
  winrate: number;  // 0.0–1.0
  score: number;    // black lead in points
}

export const mockGameState = {
  gameTitle: 'AI对弈 (自由)',
  blackName: '张三',
  blackRank: '2D',
  whiteName: 'KataGo',
  whiteRank: '5D',
  blackCaptures: 3,
  whiteCaptures: 5,
  // Legacy fields — used by ResearchPage
  winRate: 56.3,
  bestMove: 'R16',
  bestMoveProb: 94.2,
  altMove: 'Q3',
  altMoveProb: 3.1,
  blackTimer: {
    mainTimeLeft: 342,
    byoyomiLeft: 30,
    periodsLeft: 3,
    isActive: true,
    isWarning: false,
    isCritical: false,
  } as KioskTimerState,
  whiteTimer: {
    mainTimeLeft: 289,
    byoyomiLeft: 30,
    periodsLeft: 3,
    isActive: false,
    isWarning: false,
    isCritical: false,
  } as KioskTimerState,
  ruleset: '日本',
  komi: 6.5,
  currentWinrate: 0.466,
  currentScore: -0.4,
  moveNumber: 42,
  currentMoveIndex: 42,
  analysisHistory: [
    { moveIndex: 1, winrate: 0.50, score: 0.0 },
    { moveIndex: 4, winrate: 0.52, score: 0.3 },
    { moveIndex: 8, winrate: 0.48, score: -0.5 },
    { moveIndex: 12, winrate: 0.55, score: 1.2 },
    { moveIndex: 16, winrate: 0.53, score: 0.8 },
    { moveIndex: 20, winrate: 0.58, score: 2.1 },
    { moveIndex: 22, winrate: 0.45, score: -1.0 },
    { moveIndex: 25, winrate: 0.42, score: -2.3 },
    { moveIndex: 28, winrate: 0.50, score: 0.1 },
    { moveIndex: 30, winrate: 0.47, score: -0.8 },
    { moveIndex: 33, winrate: 0.44, score: -1.5 },
    { moveIndex: 36, winrate: 0.49, score: -0.2 },
    { moveIndex: 38, winrate: 0.52, score: 0.6 },
    { moveIndex: 40, winrate: 0.48, score: -0.1 },
    { moveIndex: 42, winrate: 0.466, score: -0.4 },
  ] as KioskAnalysisPoint[],
};

export const mockTsumegoProblems = [
  { id: 'beginner-1', label: '入门 1', level: '入门', solved: true, attempts: 2, lastDuration: 15,
    initialBlack: ['pp', 'qp', 'oq'], initialWhite: ['qo', 'ro', 'qn'] },
  { id: 'beginner-2', label: '入门 2', level: '入门', solved: true, attempts: 1, lastDuration: 8,
    initialBlack: ['cp', 'dp', 'dq'], initialWhite: ['co', 'do', 'cn'] },
  { id: 'beginner-3', label: '入门 3', level: '入门', solved: false, attempts: 3, lastDuration: undefined,
    initialBlack: ['op', 'pp', 'pq'], initialWhite: ['oq', 'nq', 'oo'] },
  { id: 'beginner-4', label: '入门 4', level: '入门', solved: false, attempts: 0, lastDuration: undefined,
    initialBlack: ['cq', 'dq', 'dr'], initialWhite: ['cp', 'dp', 'cr'] },
  { id: 'elementary-1', label: '初级 1', level: '初级', solved: true, attempts: 4, lastDuration: 32,
    initialBlack: ['qd', 'rd', 'qe'], initialWhite: ['qc', 'rc', 'pd'] },
  { id: 'elementary-2', label: '初级 2', level: '初级', solved: false, attempts: 1, lastDuration: undefined,
    initialBlack: ['cd', 'dd', 'ce'], initialWhite: ['cc', 'dc', 'bd'] },
  { id: 'elementary-3', label: '初级 3', level: '初级', solved: false, attempts: 0, lastDuration: undefined,
    initialBlack: ['pc', 'qc', 'pd'], initialWhite: ['ob', 'pb', 'oc'] },
  { id: 'elementary-4', label: '初级 4', level: '初级', solved: false, attempts: 0, lastDuration: undefined,
    initialBlack: ['rp', 'rq', 'sp'], initialWhite: ['ro', 'so', 'rn'] },
  { id: 'intermediate-1', label: '中级 1', level: '中级', solved: false, attempts: 0, lastDuration: undefined,
    initialBlack: ['qd', 'rd', 'qe', 'pe'], initialWhite: ['qc', 'rc', 'pd', 'od'] },
  { id: 'intermediate-2', label: '中级 2', level: '中级', solved: false, attempts: 0, lastDuration: undefined,
    initialBlack: ['pp', 'qp', 'oq', 'pq'], initialWhite: ['qo', 'ro', 'qn', 'on'] },
  { id: 'advanced-1', label: '高级 1', level: '高级', solved: false, attempts: 0, lastDuration: undefined,
    initialBlack: ['qq', 'rq', 'qr', 'pr', 'or'], initialWhite: ['qp', 'rp', 'qo', 'po', 'oq'] },
  { id: 'advanced-2', label: '高级 2', level: '高级', solved: false, attempts: 0, lastDuration: undefined,
    initialBlack: ['cd', 'dd', 'ce', 'de', 'cf'], initialWhite: ['cc', 'dc', 'bd', 'be', 'bf'] },
];

export const mockTsumegoLevels = [
  { id: '15k', rank: '15K', totalProblems: 1000,
    categories: [{ name: '官子', count: 1 }, { name: '手筋', count: 139 }, { name: '对杀', count: 63 }, { name: '吃子', count: 630 }, { name: '死活', count: 167 }] },
  { id: '14k', rank: '14K', totalProblems: 988,
    categories: [{ name: '对杀', count: 124 }, { name: '吃子', count: 295 }, { name: '手筋', count: 142 }, { name: '死活', count: 427 }] },
  { id: '13k', rank: '13K', totalProblems: 1000,
    categories: [{ name: '死活', count: 351 }, { name: '对杀', count: 238 }, { name: '吃子', count: 224 }, { name: '手筋', count: 187 }] },
  { id: '12k', rank: '12K', totalProblems: 984,
    categories: [{ name: '吃子', count: 158 }, { name: '手筋', count: 205 }, { name: '对杀', count: 215 }, { name: '死活', count: 406 }] },
  { id: '11k', rank: '11K', totalProblems: 986,
    categories: [{ name: '死活', count: 479 }, { name: '官子', count: 1 }, { name: '对杀', count: 184 }, { name: '吃子', count: 124 }, { name: '手筋', count: 198 }] },
  { id: '10k', rank: '10K', totalProblems: 983,
    categories: [{ name: '手筋', count: 203 }, { name: '死活', count: 519 }, { name: '对杀', count: 179 }, { name: '吃子', count: 82 }] },
  { id: '9k', rank: '9K', totalProblems: 984,
    categories: [{ name: '死活', count: 501 }, { name: '吃子', count: 63 }, { name: '对杀', count: 193 }, { name: '手筋', count: 227 }] },
  { id: '8k', rank: '8K', totalProblems: 985,
    categories: [{ name: '死活', count: 540 }, { name: '对杀', count: 182 }, { name: '吃子', count: 38 }, { name: '手筋', count: 224 }, { name: '官子', count: 1 }] },
  { id: '7k', rank: '7K', totalProblems: 984,
    categories: [{ name: '手筋', count: 236 }, { name: '死活', count: 564 }, { name: '吃子', count: 14 }, { name: '对杀', count: 170 }] },
  { id: '6k', rank: '6K', totalProblems: 990,
    categories: [{ name: '对杀', count: 181 }, { name: '死活', count: 609 }, { name: '手筋', count: 192 }, { name: '吃子', count: 8 }] },
  { id: '5k', rank: '5K', totalProblems: 987,
    categories: [{ name: '手筋', count: 198 }, { name: '吃子', count: 3 }, { name: '死活', count: 645 }, { name: '对杀', count: 141 }] },
  { id: '4k', rank: '4K', totalProblems: 993,
    categories: [{ name: '吃子', count: 3 }, { name: '对杀', count: 113 }, { name: '手筋', count: 171 }, { name: '死活', count: 706 }] },
];

export const mockKifuList = [
  { id: 'kifu-1', playerBlack: '柯洁', blackRank: '九段', playerWhite: '申真谞', whiteRank: '九段',
    event: '2024 LG杯决赛', result: 'W+R', moveCount: 211, datePlayed: '2024-12-15' },
  { id: 'kifu-2', playerBlack: '李昌镐', blackRank: '九段', playerWhite: '曹薰铉', whiteRank: '九段',
    event: '第18届三星杯', result: 'B+3.5', moveCount: 267, datePlayed: '2024-11-20' },
  { id: 'kifu-3', playerBlack: '张三', blackRank: '2D', playerWhite: 'KataGo', whiteRank: '5D',
    event: '自由对弈', result: 'W+12.5', moveCount: 184, datePlayed: '2025-01-05' },
  { id: 'kifu-4', playerBlack: '朴廷桓', blackRank: '九段', playerWhite: '芝野虎丸', whiteRank: '九段',
    event: '春兰杯半决赛', result: 'B+R', moveCount: 156, datePlayed: '2024-10-08' },
  { id: 'kifu-5', playerBlack: '一力辽', blackRank: '九段', playerWhite: '申真谞', whiteRank: '九段',
    event: '应氏杯决赛第1局', result: 'W+2.5', moveCount: 302, datePlayed: '2024-09-12' },
];

export const mockResearchState = {
  boardSize: 19,
  rules: 'chinese',
  komi: 7.5,
  handicap: 0,
  playerBlack: '',
  playerWhite: '',
  currentMove: 0,
  totalMoves: 0,
};

export const mockLiveMatches = [
  { id: 'live-1', black: '柯洁 九段', white: '朴廷桓 九段', event: '春兰杯半决赛', move: 127, status: 'live' as const },
  { id: 'live-2', black: '申真谞 九段', white: '芝野虎丸 九段', event: '应氏杯四分之一决赛', move: 89, status: 'live' as const },
  { id: 'live-3', black: '一力辽 九段', white: '卞相壹 九段', event: 'LG杯八强', move: 0, status: 'upcoming' as const },
];
