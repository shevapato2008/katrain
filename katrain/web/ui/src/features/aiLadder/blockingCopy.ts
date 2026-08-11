import { i18n } from '../../i18n';
import { formatCountdown } from './countdown';
import type { AiLadderBlockingGame, AiLadderSettlementSync } from './types';

/**
 * 「有一局挡着新局」这块面板上的每一句话 —— galaxy 和 kiosk 共用同一份。
 *
 * 两块屏视觉完全不同(1440x900 的双栏卡片 / 1024x600 的触屏),但它们说的**后果**必须
 * 逐字相同:同一个账号、同一把占位锁,按下去发生的事是同一件。曾经这几个函数只长在
 * galaxy 里,kiosk 那块屏干脆没有这一格;补 kiosk 的时候把文案抄一份过去,就等于给
 * 「按下去会发生什么」立了两个版本 —— 而 eslint 的 kiosk↛galaxy 边界保证了它们再也
 * 不会互相看见,漂了也没人会发现。
 *
 * 每句都走 `i18n.t(key, 中文)`:中文同时是源文和兜底,所以现在一个 .po 都不用改,
 * 而 kiosk 那块按语言切换的屏不会漏掉这一格。读这些字符串的组件**必须**调
 * `useTranslation()`,那个 hook 才是语言切换时让它重渲染的东西。
 */

/** 状态徽章:一个词说清这一局现在是什么。 */
export const blockingStateChip = (game: AiLadderBlockingGame, resumable: boolean) => {
  // 「结算中」这三个字对送不出去的成绩是句假话 —— 没有人在结算,是送不到。
  if (game.state === 'pending_settlement') {
    return { label: i18n.t('ladder:blocking_chip_undelivered', '成绩未送达'), color: 'warning' as const };
  }
  if (game.state === 'reserved') {
    return { label: i18n.t('ladder:blocking_chip_never_started', '未开始'), color: 'default' as const };
  }
  if (game.ownership === 'other_device') {
    // **不能说「对局中」。** 云端知道的只有「预约还在」,它**不知道那台机器上棋下没下完** ——
    // 已经下完、结果卡在那台自己的发送队列里时,云端照样报 `active`。
    // 通则:描述「这台设备能不能做某事」的徽标是安全的;描述「那个远端对象是什么状态」的
    // 会变成假话。换个两种情形下都真的词,而不是加一层分支 —— 分支是可以被写错的东西。
    return { label: i18n.t('ladder:blocking_chip_unsettled', '未了结'), color: 'warning' as const };
  }
  return resumable
    ? { label: i18n.t('ladder:blocking_chip_playing', '对局中'), color: 'success' as const }
    : { label: i18n.t('ladder:blocking_chip_interrupted', '已中断'), color: 'warning' as const };
};

/** 这一局现在是怎么回事 —— 一句陈述,不含动作。 */
export const blockingCopy = (game: AiLadderBlockingGame, resumable: boolean): string => {
  if (game.state === 'pending_settlement') {
    return i18n.t('ladder:blocking_body_undelivered', '这一局已经下完，成绩还没送到云端。');
  }
  if (game.state === 'reserved') {
    return i18n.t('ladder:blocking_body_never_started', '这一局登记了，但棋盘没能开起来 —— 两边都没有人在下。');
  }
  if (game.ownership === 'other_device') {
    // 同上:「正在进行」是云端猜不出来的。它可能已经下完了,只是结果还没传上来。
    // 而这句假话偏偏是在用户要为它付一场负的那一刻说的。
    return i18n.t('ladder:blocking_body_other_device', '这一局在你的另一台设备上，还没了结。');
  }
  return resumable
    ? i18n.t('ladder:blocking_body_unfinished', '你有一局正式对局尚未结束。')
    : i18n.t('ladder:blocking_body_interrupted', '这一局在本机开始，但本机的对局进程已经不在了 —— 接不回来。');
};

export interface AiLadderDisplaceCopy {
  color: 'warning' | 'error';
  button: string;
  cost: string;
  title: string;
  confirm: string;
  body: string;
}

/**
 * 让位这件事按下去会发生什么 —— 按钮、代价、二次确认,五句话一起算,免得它们各自漂走。
 *
 * **有棋盘的那两格只有一个价钱。** 曾经这里按「成绩还在送」分过一次叉(那条什么都不记),
 * 而同一处境两个价钱会让贵的那条自然消亡:劣势局面下走另一台设备免罚,严格优于当场认输,
 * 不需要恶意、只需要看得见。2026-08-11 合成一条。
 *
 * **`reserved` 不是第二个价钱,是另一件事。** 那一格云端登记了、棋盘没能开起来,两端都
 * 还没有人拿到这盘棋。让掉它确实不记成绩;照另外两格写「记为本局负」是一句关于后果的假话,
 * 而且往贵了说 —— 用户会因此干等那 5 分钟的自动回收,或者以为自己必须先输一场。
 *
 * 成绩已在传输的那一格必须明说「会覆盖真实结果」,并把用户指回「立即重试」:那才是保住
 * 那一局的路,认输是放弃它。少了这句,用户会在不知道自己有别的选择时按下不可撤销的按钮。
 */
export const displaceCopy = (game: AiLadderBlockingGame): AiLadderDisplaceCopy => {
  if (game.state === 'reserved') {
    return {
      color: 'warning',
      button: i18n.t('ladder:displace_release_button', '让掉它，在这里开新局'),
      cost: i18n.t('ladder:displace_release_cost', '那一局没能开起来，让掉它不记成绩'),
      title: i18n.t('ladder:displace_release_title', '让掉那一局？'),
      confirm: i18n.t('ladder:displace_release_confirm', '确认让掉'),
      body: i18n.t(
        'ladder:displace_release_body',
        '那一局只在云端登记过，棋盘没能在任何设备上开起来。让掉它不会记成绩，也不影响升降级。',
      ),
    };
  }
  return {
    color: game.state === 'pending_settlement' ? 'warning' : 'error',
    button: i18n.t('ladder:displace_resign_button', '认输那一局，在这里开新局'),
    cost: game.state === 'active' && game.ownership === 'other_device'
      ? i18n.t('ladder:displace_resign_cost_remote', '那一局会记为本局负；它若其实已下完，真实结果会被顶掉')
      : i18n.t('ladder:displace_resign_cost', '那一局会记为本局负，并计入升降级'),
    title: i18n.t('ladder:displace_resign_title', '认输那一局？'),
    confirm: i18n.t('ladder:displace_resign_confirm', '确认认输'),
    body: displaceBody(game),
  };
};

/**
 * 二次确认里多说的那一句 —— `active` 这一格**必须再按 `ownership` 分一次**。
 *
 * 判据:**任何按 `ownership` 分叉的文案,分叉的那一侧必须说得出「这一格实际知道什么」。**
 *   · 本机:自己下没下完自己知道 —— 而且真下完了状态会是 `pending_settlement`、根本到不了
 *     这一格,所以对本机说「还没下完」**是真的**,可以说。
 *   · 远端:只知道预约还在。它可能已经下完、结果卡在**那台自己的**发送队列里(而云端看不见
 *     任何一台盒子的队列),所以不能说「没下完」,也必须把代价说出来。
 *
 * 照顾远端的不确定性而让本机也含糊,是另一个方向的不诚实。
 */
const displaceBody = (game: AiLadderBlockingGame): string => {
  if (game.state === 'pending_settlement') {
    return i18n.t(
      'ladder:displace_resign_body_undelivered',
      '那一局已经下完了，成绩还没送到云端。认输会以一场负替换它真实的结果，并计入升降级。'
      + '若想保住那一局的成绩，请先用「立即重试」把它送上去。此操作不可撤销。',
    );
  }
  if (game.ownership === 'other_device') {
    // 这条代价**消不掉,只能说出来**:发起认输的这台机器,架构上不可能看见另一台的发送队列
    // (守卫 2 只看本机 outbox)。所以它不是可以修的缺陷,是必须披露的代价。
    return i18n.t(
      'ladder:displace_resign_body_active_remote',
      '你在另一台设备上还有一局没有了结。在这里开新局需要先认输那一局，它将计为本局负并计入升降级。'
      + '如果那台设备上这局其实已经下完、结果还没传上来，那个结果会被这一场负顶掉。此操作不可撤销。',
    );
  }
  return i18n.t(
    'ladder:displace_resign_body_active_local',
    '你还有一局正式对局没有下完。在这里开新局需要先认输那一局，它将计为本局负并计入升降级。此操作不可撤销。',
  );
};

/**
 * outbox 对这一局成绩的据实交代那一行 —— 数全部来自盒子,一个都不是前端推的。
 *
 * `remaining` 由调用方的 `useCountdown` 在**本地**走秒(它数的是时长,所以盒子的钟偏
 * 不进这个数)。数到 0 之后改说「即将重试」而不是「正在重试」:队列是每 60 秒排空一次的
 * (`SYNC_DRAIN_INTERVAL`),到期只保证「下一轮会带上它」,不保证此刻正在发。也不许停在
 * 一个 0:00 —— 那是这块屏唯一会被当成卡死的画面。
 */
export const settlementSyncText = (sync: AiLadderSettlementSync, remaining: number | null): string => {
  const counting = remaining !== null && remaining > 0;
  if (sync.state === 'refused') {
    // **HTTP 码不上屏。** 它对棋手没有信息量,却让他以为那是「更严重」的一种错误。
    // 码仍在载荷里(`sync.last_http_status`)供排错,只是不进这句话。
    // 注意这里**没有分支** —— 无论有没有码都是同一句,所以不存在「云端不给人话就整格沉默」
    // 那个洞(去码的那一刀最容易在这里把静默漏回来)。
    return i18n.t('ladder:sync_refused', '云端拒收了这一局的成绩，再试也是同一个答复。');
  }
  if (sync.state === 'exhausted') {
    return i18n
      .t('ladder:sync_exhausted', '连试 {max} 次都没送到。恢复联网后会自动继续送。')
      .replace('{max}', String(sync.max_attempts));
  }
  if (sync.state === 'waiting' && counting) {
    return i18n
      .t('ladder:sync_waiting', '重试 {n}/{max} · {countdown} 后自动重试')
      .replace('{n}', String(sync.attempt))
      .replace('{max}', String(sync.max_attempts))
      .replace('{countdown}', formatCountdown(remaining ?? 0));
  }
  if (sync.state === 'synced') {
    return i18n.t('ladder:sync_synced', '成绩已送达，正在更新段位…');
  }
  return sync.attempt > 0
    ? i18n
      .t('ladder:sync_imminent', '重试 {n}/{max} · 即将重试…')
      .replace('{n}', String(sync.attempt))
      .replace('{max}', String(sync.max_attempts))
    : i18n.t('ladder:sync_sending', '正在把成绩送到云端…');
};

/** 这一行值不值得再按一次 —— `exhausted`(网络坏了一阵)值得,`refused`(事实上被拒)不值得。 */
export const isSyncRetryable = (sync?: AiLadderSettlementSync): boolean =>
  sync?.state === 'waiting' || sync?.state === 'exhausted';

/** 这一局还能不能在**这台机器上**接着下 —— 只有本机、在下、且云端还认得那个会话时才算。 */
export const isResumableHere = (game: AiLadderBlockingGame): boolean =>
  game.state === 'active' && game.ownership === 'current_device' && Boolean(game.session_id);
