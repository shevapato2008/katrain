import { useId, useState } from 'react';

import {
  AI_LADDER_COPY,
  formatNetScore,
  formatNetScoreValueText,
  formatOutcomeLabel,
  formatPlacementProgress,
} from '../../../features/aiLadder/copy';
import { isProvisionalSeating, isRungUnseatable } from '../../../features/aiLadder/startGate';
import type { AiLadderStatus } from '../../../features/aiLadder/types';
import { useTranslation } from '../../../hooks/useTranslation';

/**
 * 设置屏「账号与平台」里的 AI 段位 —— **外壳写法**:摘要一行 + 就地展开的几行详情。
 * 与 galaxy 那张 `features/aiLadder/AiLadderStatusCard`(MUI)并行。
 *
 * ## 为什么另起一个文件,而不是给共享件加个 `variant`
 *
 * 和 `kiosk/components/aiLadder/KioskAiLadderOpponent.tsx` 同一条理由:要换的**不是几个尺寸,
 * 是另一套视觉语言**(MUI 的 Card / Chip / LinearProgress 对 `.kiosk-row` / `.kiosk-tag`)。
 * 给共享件加一个能切换整套视觉的 prop,就是一个 prop 兼管两件事,而 galaxy 在用它。
 *
 * ⚠️ **两份视图的风险是它们会说不同的话**,而且这一屏真的说过:改之前摘要行自己写了
 * 「认证中」「本地对弈」「AI段位：」,共享卡说的是「暂定」「本机对弈」「当前段位：」。所以:
 *  · 每一句都取自 `AI_LADDER_COPY`;
 *  · 判别位取自 `startGate.ts` 的纯函数,不在这儿重写条件;
 *  · 摘要行也在这个文件里 —— `*.parity.test.tsx` 比的是「展开之后这一屏说的全部」,
 *    摘要放在外面的话,它说错话那条闸看不见。
 *
 * ## 为什么是就地展开不是弹层
 *
 * 这一屏本来就是一条滚动列表,多几行代价最小;弹层要遮罩、要焦点陷阱,
 * 而 `.kiosk` 画布是缩放的 —— portal 到 body 的层不吃那个缩放。
 *
 * ## 和共享卡登记在案的一处不同
 *
 * **不画「AI升降级对弈」那行卡片标题**:这几行在「账号与平台」组里,摘要行自己就写着段位。
 */
const KioskAiLadderRows = ({ status, onRetry }: { status: AiLadderStatus; onRetry?: () => void }) => {
  // AI_LADDER_COPY 每一句都是 getter;没有这一行,语言切换后它们还念着首次渲染时那一种。
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const detailId = useId();

  if (status.view_state === 'loading') {
    return (
      <div className="kiosk-row" data-testid="ai-ladder-account-fallback" role="status" aria-live="polite">
        <span className="kiosk-row__t"><b>{AI_LADDER_COPY.loading}</b></span>
      </div>
    );
  }

  if (status.view_state === 'error') {
    return (
      <div className="kiosk-row" data-testid="ai-ladder-account-fallback">
        <span className="kiosk-row__t"><b role="alert">{status.message || AI_LADDER_COPY.loadError}</b></span>
        <span className="kiosk-row__end">
          {/* 重试**永远画得出来**(拿不到 onRetry 时禁用)—— 一颗时有时无的键比灰着更让人以为屏坏了。 */}
          <button type="button" className="kiosk-btn kiosk-btn--pill" onClick={onRetry} disabled={!onRetry}>
            {AI_LADDER_COPY.retry}
          </button>
        </span>
      </div>
    );
  }

  const placement = status.placement_state;
  const entry = placement.phase === 'placed' ? placement.rung : status.current_opponent;
  // 判别位问共享的那两个纯函数 —— 共享卡以前自己内联过一次,正是它俩被抽出来要终结的那种走散。
  const unseatable = isRungUnseatable(status);
  const provisional = isProvisionalSeating(status);
  const score = status.net_score;
  const recent = status.recent_ranked_results.slice(-5);

  return (
    <>
      <div className="kiosk-row" data-testid="ai-ladder-account-summary">
        <span className="kiosk-row__t">
          <b>
            {placement.phase === 'placed'
              ? `${AI_LADDER_COPY.currentRankPrefix}${placement.rung.rank_name}`
              : formatPlacementProgress(placement.completed_games, placement.total_games)}
          </b>
          <em>{formatNetScore(score)}</em>
        </span>
        <span className="kiosk-row__end">
          {entry && (
            <>
              <span className={entry.certification_status === 'certified' ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag kiosk-tag--warn'}>
                {AI_LADDER_COPY.certification[entry.certification_status]}
              </span>
              <span className="kiosk-tag">{AI_LADDER_COPY.route[entry.route]}</span>
            </>
          )}
          <button
            type="button"
            className="kiosk-btn kiosk-btn--pill"
            aria-expanded={open}
            aria-controls={detailId}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? t('settings:ladder_detail_close', '收起') : t('settings:ladder_detail_open', '查看AI段位详情')}
          </button>
        </span>
      </div>

      {open && (
        <div className="ladder-detail" id={detailId} data-testid="ladder-detail">
          {placement.phase === 'placement' && status.current_opponent && (
            <div className="kiosk-row">
              <span className="kiosk-row__t">
                <b>{`${AI_LADDER_COPY.currentOpponentPrefix}${status.current_opponent.rank_name}`}</b>
              </span>
            </div>
          )}

          <div className="kiosk-row">
            <span className="kiosk-row__t"><b>{formatNetScore(score)}</b></span>
            <span className="kiosk-row__end ladder-meter">
              <em>{AI_LADDER_COPY.demotionThreshold}</em>
              {/* -3 … +3 七格,中间那格是 0。从 0 往分数那一侧点亮 —— 离升段 / 降段还差几盘,一眼看得出来。 */}
              <span
                className="ladder-meter__pips"
                role="meter"
                aria-label={AI_LADDER_COPY.netScoreMeterLabel}
                aria-valuemin={-3}
                aria-valuemax={3}
                aria-valuenow={score}
                aria-valuetext={formatNetScoreValueText(score)}
              >
                {[-3, -2, -1, 0, 1, 2, 3].map((v) => (
                  <i
                    key={v}
                    data-zero={v === 0 || undefined}
                    data-on={(v > 0 && v <= score) || (v < 0 && v >= score) ? (v > 0 ? 'up' : 'down') : undefined}
                  />
                ))}
              </span>
              <em>{AI_LADDER_COPY.promotionThreshold}</em>
            </span>
          </div>

          <div className="kiosk-row">
            <span className="kiosk-row__t">
              <b>{AI_LADDER_COPY.recentResultsHeading}</b>
              <em>{AI_LADDER_COPY.recentResultsNote}</em>
            </span>
            <span className="kiosk-row__end">
              {recent.length > 0 ? (
                <ul className="ladder-recent" aria-label={AI_LADDER_COPY.recentResults}>
                  {recent.map((outcome, index) => (
                    <li
                      key={`${outcome}-${index}`}
                      className={outcome === 'win' ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag kiosk-tag--loss'}
                      aria-label={formatOutcomeLabel(index, outcome)}
                    >
                      {AI_LADDER_COPY.outcome[outcome]}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className="kiosk-tag">{AI_LADDER_COPY.noRecentResults}</span>
              )}
            </span>
          </div>

          {/* 三条提醒,条件与优先级和共享卡一字不差:成绩在途时另两条不说(那时说什么都可能过期)。 */}
          {status.pending_settlement && (
            <div className="kiosk-row">
              <span className="kiosk-row__t"><b data-sev="warn">{AI_LADDER_COPY.pendingSettlement}</b></span>
            </div>
          )}
          {unseatable && !status.pending_settlement && (
            <div className="kiosk-row">
              <span className="kiosk-row__t"><b data-sev="warn">{AI_LADDER_COPY.unavailable}</b></span>
            </div>
          )}
          {provisional && !status.pending_settlement && (
            <div className="kiosk-row">
              <span className="kiosk-row__t"><b data-sev="warn">{AI_LADDER_COPY.provisionalSeating}</b></span>
            </div>
          )}
        </div>
      )}
    </>
  );
};

export default KioskAiLadderRows;
