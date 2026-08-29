import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import PlayerCard from './PlayerCard';

// NB: PlayerInfo.calculated_rank is typed string|null (pre-existing quirk — do NOT pass a raw
// number here or tsc fails). rank_display is optional. Keep fixtures type-valid.
const ladderInfo = {
  player_type: 'player:ai', player_subtype: 'ai:ladder', name: 'AI (棋力阶梯)',
  calculated_rank: null, rank_display: '超越职业', periods_used: 0, main_time_used: 0,
};
const humanInfo = {
  player_type: 'human', player_subtype: '', name: 'User',
  calculated_rank: null, periods_used: 0, main_time_used: 0,  // rank_display omitted (optional)
};

describe('PlayerCard rank_display', () => {
  it('shows rank_display 段位 when present (ladder AI)', () => {
    render(<PlayerCard player="W" info={ladderInfo} captures={0} active={false} />);
    expect(screen.getByText('超越职业')).toBeInTheDocument();
    expect(screen.getByText('AI (棋力阶梯)')).toBeInTheDocument();
  });

  it('falls back to the calculated-rank path when rank_display is absent', () => {
    render(<PlayerCard player="B" info={humanInfo} captures={0} active={false} />);
    // rank_display absent + calculated_rank null -> "No Rank": proves `??` falls through, no 段位 leak
    expect(screen.getByText('No Rank')).toBeInTheDocument();
    expect(screen.queryByText('超越职业')).not.toBeInTheDocument();
  });
});

/* 两条容器带别再被合回一条。
   2026-08-30 右栏从 380 加宽到 520 之前，字号收窄和「我在右栏里」共用 899 一条带；
   加宽之后 520 档里每张卡有 244 却还按 140 的字号画。这条钉的就是那次拆分：
   **收窄归 460、语义归 899**。变异验证：把 RAIL_TIGHT 改回 899，第二条断言红
   （emit 出来的样式里再也找不到 460 那条带）。 */
describe('PlayerCard 的两条 board-rail 容器带', () => {
  const emittedCss = () => Array.from(document.querySelectorAll('style'))
    .map((node) => node.textContent ?? '').join('\n');

  it('keeps the in-rail semantics on the 899 band and the size compaction on the 460 band', () => {
    render(<PlayerCard player="B" info={humanInfo} captures={0} active />);
    const css = emittedCss();
    expect(css).toContain('@container board-rail (max-width: 899px)');
    expect(css).toContain('@container board-rail (max-width: 460px)');
  });
});

