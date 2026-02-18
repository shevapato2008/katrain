// Fixed mock data — deterministic, no Math.random(). Used across remaining kiosk pages.

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
