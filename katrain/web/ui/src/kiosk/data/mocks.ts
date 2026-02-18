// Fixed mock data — deterministic, no Math.random(). Used across remaining kiosk pages.

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
