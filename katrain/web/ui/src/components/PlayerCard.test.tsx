import { act, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, it, expect, vi } from 'vitest';
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

describe('PlayerCard server clock snapshots', () => {
  beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2026-10-09T00:00:00Z')); });
  afterEach(() => vi.useRealTimers());
  const timer = (used: number) => ({
    paused: false, main_time_used: 0, current_node_time_used: used, next_player_periods_used: 0,
    settings: { main_time: 0, byo_length: 30, byo_periods: 5, sound: false },
  });

  it('does not count elapsed time twice when an authoritative byoyomi snapshot arrives', () => {
    const { rerender } = render(<PlayerCard player="B" info={humanInfo} captures={0} active timer={timer(10)} />);
    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByText('18s')).toBeInTheDocument();
    rerender(<PlayerCard player="B" info={humanInfo} captures={0} active timer={timer(12)} />);
    expect(screen.getByText('18s')).toBeInTheDocument();
    rerender(<PlayerCard player="B" info={{ ...humanInfo, periods_used: 1 }} captures={0} active timer={timer(1)} />);
    expect(screen.getByText('29s')).toBeInTheDocument();
  });

  it('keeps interpolating when only non-clock display data changes', () => {
    const { rerender } = render(<PlayerCard player="B" info={humanInfo} captures={0} active timer={timer(10)} />);
    act(() => vi.advanceTimersByTime(2000));
    rerender(<PlayerCard player="B" info={humanInfo} captures={1} active timer={timer(10)} />);
    expect(screen.getByText('18s')).toBeInTheDocument();
  });

  it('does not trigger timeout from stale interpolation on a valid last-period snapshot', () => {
    const onTimeout = vi.fn();
    const info = { ...humanInfo, periods_used: 4 };
    const { rerender } = render(<PlayerCard player="B" info={info} captures={0} active timer={timer(24)} onTimeout={onTimeout} />);
    act(() => vi.advanceTimersByTime(2000));
    rerender(<PlayerCard player="B" info={info} captures={0} active timer={timer(29)} onTimeout={onTimeout} />);
    expect(screen.getByText('1s')).toBeInTheDocument();
    expect(onTimeout).not.toHaveBeenCalled();
  });

  it('does not apply the active player node time to the inactive player', () => {
    render(<PlayerCard player="W" info={humanInfo} captures={0} active={false} timer={timer(12)} />);
    expect(screen.getByText('30s')).toBeInTheDocument();
  });
});

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

