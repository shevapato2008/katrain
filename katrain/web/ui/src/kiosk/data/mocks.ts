// Fixed mock data — deterministic, no Math.random(). Used across all kiosk pages.

export const mockGameState = {
  blackPlayer: '张三 (2D)',
  whitePlayer: 'KataGo 5D',
  blackCaptures: 3,
  whiteCaptures: 5,
  winRate: 56.3,
  bestMove: 'R16',
  bestMoveProb: 94.2,
  altMove: 'Q3',
  altMoveProb: 3.1,
  moveNumber: 42,
};

export const mockTsumegoProblems = [
  { id: 'beginner-1', label: '入门 1', level: '入门', solved: true },
  { id: 'beginner-2', label: '入门 2', level: '入门', solved: true },
  { id: 'beginner-3', label: '入门 3', level: '入门', solved: false },
  { id: 'beginner-4', label: '入门 4', level: '入门', solved: false },
  { id: 'elementary-1', label: '初级 1', level: '初级', solved: true },
  { id: 'elementary-2', label: '初级 2', level: '初级', solved: false },
  { id: 'elementary-3', label: '初级 3', level: '初级', solved: false },
  { id: 'elementary-4', label: '初级 4', level: '初级', solved: false },
  { id: 'intermediate-1', label: '中级 1', level: '中级', solved: false },
  { id: 'intermediate-2', label: '中级 2', level: '中级', solved: false },
  { id: 'advanced-1', label: '高级 1', level: '高级', solved: false },
  { id: 'advanced-2', label: '高级 2', level: '高级', solved: false },
];

export const mockKifuList = [
  { id: 'kifu-1', black: '柯洁 九段', white: '申真谞 九段', event: '2024 LG杯决赛', result: 'W+R' },
  { id: 'kifu-2', black: '李昌镐 九段', white: '曹薰铉 九段', event: '第18届三星杯', result: 'B+3.5' },
  { id: 'kifu-3', black: '张三 2D', white: 'KataGo 5D', event: '自由对弈', result: 'W+12.5' },
];

export const mockLiveMatches = [
  { id: 'live-1', black: '柯洁 九段', white: '朴廷桓 九段', event: '春兰杯半决赛', move: 127, status: 'live' as const },
  { id: 'live-2', black: '申真谞 九段', white: '芝野虎丸 九段', event: '应氏杯四分之一决赛', move: 89, status: 'live' as const },
  { id: 'live-3', black: '一力辽 九段', white: '卞相壹 九段', event: 'LG杯八强', move: 0, status: 'upcoming' as const },
];
