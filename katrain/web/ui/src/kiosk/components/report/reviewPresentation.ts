import type { ReportGameStatus } from '../../../features/report/reportModel';
import type { UserGameSummary } from '../../../api/userGamesApi';
import { isRankedGameType } from '../../../features/aiLadder/gameType';
import { interpolate } from '../../utils/interpolate';

export type TFn = (key: string, fallback?: string) => string;

/**
 * 「目 / 子」。**不复用 `resultTranslation` 里那个** —— 它缺省返回空字符串,而
 * `t(key, '')` 在翻译表没加载时会退回 **key 本身**,屏上就出现「负 6.5result:points_zi」
 * (2026-08-23 四图里真的出现过)。缺省值必须是能直接上屏的字。
 */
function pointsUnit(rules: string | null | undefined, t: TFn): string {
  const r = (rules || '').toLowerCase();
  if (r === 'chinese' || r === 'cn') return t('result:points_zi', '子');
  if (r === 'japanese' || r === 'jp' || r === 'korean' || r === 'ko') return t('result:points_moku', '目');
  return '';
}

/**
 * 屏 19「历史对局」每一行怎么念。**纯函数,单测在 `reviewPresentation.test.ts`** ——
 * 这些判断全是「这一局是什么」的推断,错了屏上看不出来(一句通顺的中文说的是另一局),
 * 只能靠断言钉。
 */

/**
 * 这一局里哪一方是「你」。
 *
 * 判据是**存谱时写进去的东西**,不是猜的:人机局存谱时人这一方填的是当前用户名、
 * AI 那方填的是 AI 的名字(`web/server.py:1435-1452`)。所以名字对得上就是你。
 *
 * **两类局没有「你」,而且它们在这台盒子上真会出现**:
 *   `play_local` —— 两个人面对面下的,两边都是你,没有单一视角;
 *   `import` / `kifu_library` —— 别人下的谱。
 * 这时候返回 `null`,**不许挑一方冒充你** —— 「你(黑)中盘负」写在一局你没下过的棋上,
 * 是这一屏最容易犯、也最难被发现的错。
 */
export function yourColor(game: UserGameSummary, username?: string | null): 'B' | 'W' | null {
  if (game.source !== 'play_ai' && game.source !== 'play_human') return null;
  if (!username) return null;
  if (game.player_black === username) return 'B';
  if (game.player_white === username) return 'W';
  return null;
}

const seat = (game: UserGameSummary, color: 'B' | 'W') => ({
  name: color === 'B' ? game.player_black : game.player_white,
  rank: color === 'B' ? game.black_rank : game.white_rank,
});

function opponentLabel(game: UserGameSummary, mine: 'B' | 'W' | null): string | null {
  if (!mine) return null;
  const other = seat(game, mine === 'B' ? 'W' : 'B');
  if (!other.name) return null;
  return other.rank ? `${other.name} · ${other.rank}` : other.name;
}

/** 行首那颗子的颜色。没有「你」的局用黑白各半 —— 拿黑或白顶替等于替它选了一方。 */
export function rowDisc(mine: 'B' | 'W' | null): 'b' | 'w' | 'rnd' {
  return mine === 'B' ? 'b' : mine === 'W' ? 'w' : 'rnd';
}

/**
 * 行的标题。**计分局必须认得出来** —— 它和自由对弈进的是同一条复盘线、同一份报告,
 * 区别只在这一局算不算分(国象 2026-07-28 拍板,写在 `sample-chess` 的注释里)。
 * 长成一个样的话,回头看「我那盘定段赛下得怎么样」就找不着了。
 */
export function rowTitle(game: UserGameSummary, mine: 'B' | 'W' | null, t: TFn): string {
  if (game.source === 'kifu_library') {
    return game.event || game.title || t('review:row_library', '棋谱库');
  }
  if (game.source === 'import') {
    const name = game.title || game.event;
    return name ? `${t('review:row_import', '导入的棋谱')} · ${name}` : t('review:row_import', '导入的棋谱');
  }
  if (game.source === 'play_local') return t('review:row_local', '本地对局 · 两人');
  // 判不出「你」的时候没有「对手」可言,退回两个名字并排 —— 不挑一方当对手。
  const opponent = opponentLabel(game, mine)
    || [game.player_black, game.player_white].filter(Boolean).join(' — ');
  if (isRankedGameType(game.game_type)) {
    return opponent
      ? `${t('review:row_ranked', '升降级对弈')} · ${opponent}`
      : t('review:row_ranked', '升降级对弈');
  }
  if (game.source === 'play_human') {
    return opponent ? `${t('review:row_human', '人人对局')} · ${opponent}` : t('review:row_human', '人人对局');
  }
  return opponent ? `${t('review:row_vs', 'vs')} ${opponent}` : t('review:row_ai', '人机对弈');
}

/**
 * 「你(黑)中盘负」/「黑中盘胜」/「下到第 22 手就退出了」。
 *
 * 没有 `result` 就是**没下完**,不是「和棋」也不是「不知道」—— 这一格照实说。
 */
export function outcomeLine(game: UserGameSummary, mine: 'B' | 'W' | null, t: TFn): string {
  const raw = (game.result || '').trim();
  if (!raw) {
    return interpolate(t('review:unfinished_line', '下到第 {n} 手就退出了'), { n: game.move_count });
  }
  const m = raw.match(/^([BW])\+(.+)$/i);
  if (!m) return raw;                       // 后端存了别的写法就原样念,不猜
  const winner = m[1].toUpperCase() as 'B' | 'W';
  const detail = m[2];
  const win = t('review:win', '胜');
  const lose = t('review:lose', '负');
  const colorZh = (c: 'B' | 'W') => (c === 'B' ? t('review:black', '黑') : t('review:white', '白'));

  let by: string | null = null;             // 中盘 / 超时 / 弃权
  if (/^R(esign(ation)?)?$/i.test(detail)) by = t('review:by_resign', '中盘');
  else if (/^T(ime)?$/i.test(detail)) by = t('review:by_time', '超时');
  else if (/^F(orfeit)?$/i.test(detail)) by = t('review:by_forfeit', '弃权');

  const pts = parseFloat(detail);
  // 「6.5 子」中间那个空格是稿子上的写法;规则给不出单位时不留一个悬空的空格。
  const points = by == null && !Number.isNaN(pts)
    ? [String(pts), pointsUnit(game.rules, t)].filter(Boolean).join(' ')
    : null;

  if (mine) {
    const verb = winner === mine ? win : lose;
    const who = `${t('review:you', '你')}(${colorZh(mine)})`;
    if (by) return `${who}${by}${verb}`;                    // 你(黑)中盘负
    if (points) return `${who}${verb} ${points}`;           // 你(白)负 6.5 目
    return `${who}${verb}`;
  }
  if (by) return `${colorZh(winner)}${by}${win}`;           // 黑中盘胜
  if (points) return `${colorZh(winner)}${win} ${points}`;  // 白胜 2.5 目
  return `${colorZh(winner)}${win}`;
}

export type RowState =
  /** `taskIds` 按档给全 —— 两档都跑完时**没有唯一宾语**,行尾得拆成两个键。 */
  | { kind: 'analyzed'; taskId: number; taskIds: readonly { tier: 'normal' | 'deep'; id: number }[] }
  | { kind: 'running'; taskId: number; analyzed: number; total: number }
  | { kind: 'partial'; taskId: number; analyzed: number; total: number }
  | { kind: 'failed'; taskId: number }
  | { kind: 'unanalyzed' }
  | { kind: 'unfinished' };

/**
 * 这一局的分析到哪一步了。规范 §11 要求**四种状态各有各的样子**,
 * 「算了一半没算完」最容易被糊弄成「已分析」——它必须自己一档。
 *
 * 后端没有「暂停」这个状态:跑了一半断掉的任务落在 `failed` 上,
 * 而 `analyzed_moves` 还留着。**所以 `failed` 要按有没有进度分成两档** ——
 * 有进度的那档重试会从断点续算(`cron/jobs/report_analyze.py:195` 的 `_get_resume_move_number`),
 * 说「继续分析」是准的,说「重试」反而像要从头再来。
 */
export function rowState(game: UserGameSummary, state: ReportGameStatus): RowState {
  const done = state.completedDeep ?? state.completedNormal;
  if (done) {
    // ⚠️ **`taskId` 按档发,同一局可以同时挂着标准和精读两份完成报告** ——
    // 那时一个「查看报告」键指不了两个 id。`taskId` 保留成「最细的那一份」(深读优先),
    // `taskIds` 把两档都带出来,由行尾决定是画一个键还是两个。
    const taskIds = [
      state.completedNormal ? { tier: 'normal' as const, id: state.completedNormal.id } : null,
      state.completedDeep ? { tier: 'deep' as const, id: state.completedDeep.id } : null,
    ].filter((x): x is { tier: 'normal' | 'deep'; id: number } => x !== null);
    return { kind: 'analyzed', taskId: done.id, taskIds };
  }
  const active = state.activeDeep ?? state.activeNormal;
  if (active) {
    return {
      kind: 'running',
      taskId: active.id,
      analyzed: active.analyzed_moves,
      total: active.total_moves > 0 ? active.total_moves : game.move_count,
    };
  }
  const failed = state.failedDeep ?? state.failedNormal;
  if (failed) {
    if (failed.analyzed_moves > 0) {
      return {
        kind: 'partial',
        taskId: failed.id,
        analyzed: failed.analyzed_moves,
        total: failed.total_moves > 0 ? failed.total_moves : game.move_count,
      };
    }
    return { kind: 'failed', taskId: failed.id };
  }
  return game.result ? { kind: 'unanalyzed' } : { kind: 'unfinished' };
}
