/**
 * 对局钟 —— 前端**唯一一份**倒计时算法。galaxy 的 `components/PlayerCard.tsx` 和
 * kiosk 的 `kiosk/components/game/GameControlPanel.tsx` 都调它,免得两份算法走散。
 *
 * ## 与后端是同一套语义(`katrain/web/interface.py` 的 `update_timer`)
 *
 * - `byo_length` / `byo_periods` 先过 `max(1, …)`,后端就是这么取的。
 * - 读秒次数只在「这一段用满**之后还多出来**」时才扣(`>`,不是 `>=`):
 *   后端的循环是 `while cn.time_used > byo_len and periods_used < byo_num`。
 *   所以正好用到 30.0 秒那一刻**还没超时**,多一丁点才算。
 * - `nodeTimeUsed` 是后端的 `cn.time_used` —— 它**只装主时间用完之后溢出的那部分**,
 *   而且每扣一次读秒就减掉一个 `byo_length`。所以它是「本段读秒已用」,不是「这一手总共想了多久」。
 * - 超时 = 主时间剩 0 且读秒次数用满 —— 后端 `game_end_rules.is_time_exhausted` 的判据,
 *   在循环语义下读秒用尽那一刻 `periods_used` 恰好等于 `byo_periods`。
 *
 * ## 调用方的责任
 *
 * - `nodeTimeUsed` 只对**轮到的一方**有意义(后端只下发轮到方的 `current_node_time_used`)。
 *   这里**原样使用**,不按 `active` 清零 —— 那是 `PlayerCard` 抽函数之前的行为,galaxy 本轮不改;
 *   kiosk 调用方给非轮到的一方传 0。
 * - `clientElapsed` 是「上一份服务端状态到现在」客户端流逝的秒数,只在 `active` 时计入。
 */
export interface ClockSettings { main_time: number; byo_length: number; byo_periods: number } // main_time 单位：分钟
export interface ClockInput {
  settings: ClockSettings | null | undefined;
  mainTimeUsed: number;      // 秒，这一方累计
  periodsUsed: number;       // 这一方已用读秒次数
  nodeTimeUsed: number;      // 秒，当前节点已用（只对轮到的一方有意义）
  active: boolean;           // 是否轮到这一方
  clientElapsed: number;     // 秒，上次服务端状态以来客户端流逝
}
export interface ClockView {
  showTimer: boolean;
  phase: 'main' | 'byoyomi' | 'expired';
  mainTimeLeft: number;      // 秒
  byoyomiLeft: number;       // 秒
  periodsLeft: number;
}

const NO_TIMER: ClockView = { showTimer: false, phase: 'main', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 };

export function computeClock(input: ClockInput): ClockView {
  const { settings, mainTimeUsed, periodsUsed, nodeTimeUsed, active, clientElapsed } = input;
  // 「开没开用时」看的是**原始值**:不限时那一档后端写的是 main_time=0 / byo_length=0。
  // 先过 max(1, …) 再判的话,不限时的局会凭空多出一个 1 秒的读秒。
  if (!settings || !(settings.main_time > 0 || settings.byo_length > 0)) return NO_TIMER;

  const byoLen = Math.max(1, settings.byo_length);
  const byoNum = Math.max(1, settings.byo_periods);
  const mainTotal = settings.main_time * 60;

  const mainUsedNow = mainTimeUsed + (active && mainTotal > mainTimeUsed ? clientElapsed : 0);
  const mainTimeLeft = Math.max(0, mainTotal - mainUsedNow);
  if (mainTimeLeft > 0) {
    return { showTimer: true, phase: 'main', mainTimeLeft, byoyomiLeft: byoLen, periodsLeft: byoNum - periodsUsed };
  }

  // 主时间在**这份快照里**还剩多少 —— 客户端流逝里只有超出它的那部分进读秒。
  const mainAvailableAtSnapshot = Math.max(0, mainTotal - mainTimeUsed);
  const nodeTime = nodeTimeUsed + (active ? clientElapsed : 0);
  let effective = Math.max(0, nodeTime - mainAvailableAtSnapshot);
  let used = periodsUsed;
  while (effective > byoLen && used < byoNum) {
    effective -= byoLen;
    used += 1;
  }
  if (used >= byoNum) return { showTimer: true, phase: 'expired', mainTimeLeft: 0, byoyomiLeft: 0, periodsLeft: 0 };
  return { showTimer: true, phase: 'byoyomi', mainTimeLeft: 0, byoyomiLeft: Math.max(0, byoLen - effective), periodsLeft: byoNum - used };
}
