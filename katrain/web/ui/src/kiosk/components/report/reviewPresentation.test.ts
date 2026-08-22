import { describe, expect, it } from 'vitest';

import type { UserGameSummary } from '../../../api/userGamesApi';
import { outcomeLine, rowDisc, rowState, rowTitle, yourColor } from './reviewPresentation';

/**
 * 这些判断错了**屏上看不出来** —— 出来的还是一句通顺的中文,只是说的是另一局棋。
 * 所以每一条都在这儿钉住。
 */

const t = (_key: string, fallback?: string) => fallback ?? '';

const game = (over: Partial<UserGameSummary> = {}): UserGameSummary => ({
  id: 'g', user_id: 1, title: null, player_black: '阿福', player_white: 'KataGo',
  black_rank: null, white_rank: '6 级', result: 'B+R', board_size: 19, rules: 'chinese',
  komi: 7.5, move_count: 187, source: 'play_ai', category: 'game', game_type: 'free',
  event: null, round_name: null, game_date: null, created_at: null, updated_at: null,
  ...over,
});

describe('yourColor —— 哪一方是「你」', () => {
  it('人机局按存谱时写进去的用户名认', () => {
    expect(yourColor(game(), '阿福')).toBe('B');
    expect(yourColor(game({ player_black: 'KataGo', player_white: '阿福' }), '阿福')).toBe('W');
  });

  // 这两类局在盒子上真会出现,而它们**没有「你」**。挑一方冒充你 ⇒
  // 「你(黑)中盘负」会写在一局你根本没下过的棋上。
  it('本地两人对局和导进来的谱都没有「你」', () => {
    expect(yourColor(game({ source: 'play_local', player_black: '小明', player_white: '小红' }), '阿福')).toBeNull();
    expect(yourColor(game({ source: 'import' }), '阿福')).toBeNull();
    expect(yourColor(game({ source: 'kifu_library' }), '阿福')).toBeNull();
  });

  it('名字对不上、或者压根没登录名时也不猜', () => {
    expect(yourColor(game(), '别人')).toBeNull();
    expect(yourColor(game(), null)).toBeNull();
  });

  it('行首那颗子:没有「你」的用黑白各半', () => {
    expect(rowDisc('B')).toBe('b');
    expect(rowDisc('W')).toBe('w');
    expect(rowDisc(null)).toBe('rnd');
  });
});

describe('rowTitle —— 这一行是什么局', () => {
  it('自由人机写成 vs 对手 · 段位', () => {
    expect(rowTitle(game(), 'B', t)).toBe('vs KataGo · 6 级');
  });

  // 计分局必须认得出来 —— 它和自由对弈进的是同一条复盘线、同一份报告,
  // 区别只在这一局算不算分(国象 2026-07-28 拍板)。长成一个样就找不着了。
  it('计分局认得出来,不和自由对弈长成一个样', () => {
    expect(rowTitle(game({ game_type: 'ai_ladder_ranked' }), 'B', t)).toBe('升降级对弈 · KataGo · 6 级');
  });

  it('本地两人、导入谱、棋谱库各说各的', () => {
    expect(rowTitle(game({ source: 'play_local' }), null, t)).toBe('本地对局 · 两人');
    expect(rowTitle(game({ source: 'import', title: 'game-0731' }), null, t)).toBe('导入的棋谱 · game-0731');
    expect(rowTitle(game({ source: 'kifu_library', event: '第 29 届三星杯' }), null, t)).toBe('第 29 届三星杯');
  });

  it('判不出「你」的人机局把两个名字并排,不挑一方当对手', () => {
    expect(rowTitle(game(), null, t)).toBe('vs 阿福 — KataGo');
  });
});

describe('outcomeLine —— 这一局怎么结束的', () => {
  it('中盘胜负带上「你(黑)」', () => {
    expect(outcomeLine(game({ result: 'B+R' }), 'B', t)).toBe('你(黑)中盘胜');
    expect(outcomeLine(game({ result: 'B+R' }), 'W', t)).toBe('你(白)中盘负');
  });

  // 单位跟着规则走,而且**缺省值必须是能上屏的字** —— `t(key, '')` 在翻译表没加载时
  // 会退回 key 本身,四图里真的出现过「负 6.5result:points_zi」。
  it('数目的局把目数和单位放在胜负后面', () => {
    expect(outcomeLine(game({ result: 'W+6.5' }), 'B', t)).toBe('你(黑)负 6.5 子');
    expect(outcomeLine(game({ result: 'W+2.5', rules: 'japanese' }), 'W', t)).toBe('你(白)胜 2.5 目');
    // 规则认不出来时不留一个悬空的空格
    expect(outcomeLine(game({ result: 'W+2.5', rules: 'aga' }), 'W', t)).toBe('你(白)胜 2.5');
  });

  it('超时和弃权各有各的说法', () => {
    expect(outcomeLine(game({ result: 'W+T' }), 'B', t)).toBe('你(黑)超时负');
    expect(outcomeLine(game({ result: 'B+F' }), 'B', t)).toBe('你(黑)弃权胜');
  });

  it('没有「你」的局按赢家念', () => {
    expect(outcomeLine(game({ result: 'B+R' }), null, t)).toBe('黑中盘胜');
    expect(outcomeLine(game({ result: 'W+2.5' }), null, t)).toBe('白胜 2.5 子');
  });

  // 没有 result **就是没下完**,不是和棋、也不是「不知道」。
  it('没有结果的局说的是「下到第几手就退出了」', () => {
    expect(outcomeLine(game({ result: null, move_count: 22 }), 'B', t)).toBe('下到第 22 手就退出了');
  });

  it('后端存了别的写法就原样念,不猜', () => {
    expect(outcomeLine(game({ result: 'Void' }), 'B', t)).toBe('Void');
  });
});

describe('rowState —— 分析到哪一步了', () => {
  const task = (over: Record<string, unknown> = {}) => ({
    id: 7, user_game_id: 'g', status: 'completed', report_type: 'normal' as const,
    total_moves: 187, analyzed_moves: 187, requested_visits: 500, ...over,
  });

  // ⚠️ **报告是按档发的** —— 同一局可以同时挂标准和精读两份。`taskId` 取最细的那一份,
  // 但 `taskIds` 必须把两档都带出来:一个「查看报告」键指不了两个 id。
  it('两档都跑完时把两个 id 都带出来,taskId 取更细的那一份', () => {
    expect(rowState(game(), { completedNormal: task(), completedDeep: task({ id: 9 }) }))
      .toEqual({
        kind: 'analyzed',
        taskId: 9,
        taskIds: [{ tier: 'normal', id: 7 }, { tier: 'deep', id: 9 }],
      });
  });

  it('只有一档时 taskIds 也只有一条 —— 行尾据此决定画一个键还是两个', () => {
    expect(rowState(game(), { completedNormal: task() }))
      .toEqual({ kind: 'analyzed', taskId: 7, taskIds: [{ tier: 'normal', id: 7 }] });
  });

  it('正在跑的带上进度', () => {
    expect(rowState(game(), { activeNormal: task({ status: 'running', analyzed_moves: 31 }) }))
      .toEqual({ kind: 'running', taskId: 7, analyzed: 31, total: 187 });
  });

  // **「算了一半」既不是成功也不是失败。** 后端没有「暂停」这个状态:跑了一半断掉的任务
  // 落在 failed 上、`analyzed_moves` 还留着,而重试会从断点续算 —— 所以这一档说「继续」。
  it('跑了一半断掉的自己一档,不和「一手都没算成」混在一起', () => {
    expect(rowState(game(), { failedNormal: task({ status: 'failed', analyzed_moves: 96 }) }))
      .toEqual({ kind: 'partial', taskId: 7, analyzed: 96, total: 187 });
    expect(rowState(game(), { failedNormal: task({ status: 'failed', analyzed_moves: 0 }) }))
      .toEqual({ kind: 'failed', taskId: 7 });
  });

  it('任务的总手数是 0 时退回这局自己的手数 —— 不写「31/0」', () => {
    expect(rowState(game({ move_count: 240 }), { activeNormal: task({ status: 'pending', total_moves: 0, analyzed_moves: 0 }) }))
      .toEqual({ kind: 'running', taskId: 7, analyzed: 0, total: 240 });
  });

  it('没有任务时,下完的叫「未分析」、没下完的叫「未终局」', () => {
    expect(rowState(game(), {})).toEqual({ kind: 'unanalyzed' });
    expect(rowState(game({ result: null }), {})).toEqual({ kind: 'unfinished' });
  });
});
