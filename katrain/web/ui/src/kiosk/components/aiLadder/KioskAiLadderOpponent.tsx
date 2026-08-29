import { AI_LADDER_COPY, formatPlacementProgress, formatPlacementProgressLabel } from '../../../features/aiLadder/copy';
import { isProvisionalSeating, isRungUnseatable } from '../../../features/aiLadder/startGate';
import type { AiLadderStatus } from '../../../features/aiLadder/types';
import { useTranslation } from '../../../hooks/useTranslation';

/**
 * 屏 03 升降级开局设置里「对手」那一格 —— **外壳写法**。
 *
 * ## 为什么另起一个文件,而不是给共享件加个 `variant`
 *
 * `features/aiLadder/AiLadderSetupOpponent` 是 galaxy 那屏的消费者
 * (`galaxy/pages/AiSetupPage.tsx`),在原地改样式会把另一家一起改了。
 * 而这里要换的**不是几个尺寸,是另一套视觉语言**(MUI 的 Chip / LinearProgress / Alert
 * 对 `.kiosk-tag` / `.setexplain` / `.kiosk-btn`)—— `@container` 那条路子只收窄盒子,
 * 换不掉标记。给共享件加一个能切换整套视觉的 prop,就是一个 prop 兼管两件事。
 *
 * ⚠️ **两份视图的风险是它们会说不同的话。** 所以:
 *  · 每一句都取自 `AI_LADDER_COPY`,两边同源;
 *  · 六种状态的判别位取自同一组纯函数(`startGate.ts`),不在这儿重写条件;
 *  · `KioskAiLadderOpponent.parity.test.tsx` 逐状态断言**两个视图说出来的话是同一套**。
 *
 * ## 和稿子的两处不同
 *
 * ① **不画标题。** 共享件里那行 `setupTitle` 在这儿是重复的 —— 它正上方就是
 *    `<KioskSecLabel zh="对手">`,同一件事说两遍。
 *    (顺带避开一个已知过期的数:`setupTitle` 写的是「41档」,而 Fan 2026-08-13 已裁定
 *    41 → 35 档,代码至今没落地。那笔账在阶梯那条赛道上,不在这一屏。)
 * ② **已定档那一态照稿子写成一句话**:「你是 X,配到 第 N 档 —— 为什么不给挑」。
 *    共享件那边只说「本局对手:X」。两个数(`rank_name` / `rung`)都在
 *    `placement_state.rung` 里 —— 在升降级里**你的档就是你的对手**,不是两个东西。
 */
const KioskAiLadderOpponent = ({ status, onRetry }: {
  status: AiLadderStatus;
  onRetry?: () => void;
}) => {
  // AI_LADDER_COPY 每一句都是 getter;没有这一行,语言切换后它们还念着首次渲染时那一种。
  useTranslation();

  if (status.view_state === 'loading') {
    return (
      <p className="setexplain" role="status" aria-live="polite" data-testid="ladder-opponent">
        {AI_LADDER_COPY.loading}
      </p>
    );
  }

  if (status.view_state === 'error') {
    return (
      <div className="setexplain" data-testid="ladder-opponent">
        <span role="alert">{status.message || AI_LADDER_COPY.loadError}</span>
        {/* 重试**永远画得出来**(拿不到 `onRetry` 时禁用),不是有就画没有就撤 ——
            一颗时有时无的键比一颗灰着的键更让人以为「这屏坏了」。 */}
        <button
          type="button" className="kiosk-btn kiosk-btn--pill ladder-retry"
          onClick={onRetry} disabled={!onRetry}
        >
          {AI_LADDER_COPY.retry}
        </button>
      </div>
    );
  }

  const placement = status.placement_state;
  const activeEntry = placement.phase === 'placement' ? status.current_opponent : placement.rung;
  // 「不可挑战」是**服务端的回答**,不是这一档的属性:开了暂定对局的节点上,
  // 一个没标定的档是可以坐下的,而在一颗能按的键旁边说它不可挑战,正是玩家会不信的那种自相矛盾。
  const unavailable = isRungUnseatable(status) || !activeEntry;
  const provisional = isProvisionalSeating(status);

  return (
    <div data-testid="ladder-opponent">
      {placement.phase === 'placement' ? (
        <p className="setexplain">
          {/* 前缀和档名放在**同一个元素**里:拆开之后 `getByText('定级对手:9级')` 会找不到,
              而那条断言问的正是「屏上有没有这句话」—— 一句话被标记切成两半,
              对读屏和对测试都是两句。 */}
          <span>{AI_LADDER_COPY.placementOpponentPrefix}{status.current_opponent?.rank_name ?? '—'}</span>
          <br />
          {formatPlacementProgress(placement.completed_games, placement.total_games)}
          <progress
            className="ladder-progress"
            aria-label={formatPlacementProgressLabel(placement.completed_games, placement.total_games)}
            max={placement.total_games}
            value={placement.completed_games}
          />
        </p>
      ) : (
        <p className="setexplain">
          {/* 稿子那一句。两个数都出自同一份 `rung` —— 升降级里你的档就是你的对手。 */}
          你是 <b>{placement.rung.rank_name}</b>,配到 <b>第 {placement.rung.rung} 档</b>
          {' —— '}
          {AI_LADDER_COPY.boxPicksReason}。
        </p>
      )}

      {activeEntry && (
        <div className="ladder-tags">
          {/* 「暂定」是琥珀的、「已认证」是素的 —— 共享件那边同一处是 Chip 的
              warning / success,两边说的是同一件事。 */}
          <span className={activeEntry.certification_status === 'certified' ? 'kiosk-tag' : 'kiosk-tag kiosk-tag--warn'}>
            {AI_LADDER_COPY.certification[activeEntry.certification_status]}
          </span>
          <span className="kiosk-tag">{AI_LADDER_COPY.route[activeEntry.route]}</span>
        </div>
      )}

      {/* 这三条不挂 `role="status"` / `aria-live`:那是**播报进展**的语义,而这里没有进展可播 ——
          它们说的是一个停住的状态。加载那一处保留,因为那儿真有一次取数在跑。 */}
      {status.pending_settlement && (
        <p className="ladder-warn">{AI_LADDER_COPY.pendingSettlement}</p>
      )}
      {unavailable && !status.pending_settlement && (
        <p className="ladder-warn">{AI_LADDER_COPY.unavailable}</p>
      )}
      {provisional && !status.pending_settlement && (
        <p className="ladder-warn" data-testid="ladder-provisional-seating">
          {AI_LADDER_COPY.provisionalSeating}
        </p>
      )}
    </div>
  );
};

export default KioskAiLadderOpponent;
