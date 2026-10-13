import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { StrictMode, useEffect, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { MoveAnalysis } from '../../../types/live';
import MoveGradePanel from './MoveGradePanel';

vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }),
}));

afterEach(cleanup);

const analysis: Record<number, MoveAnalysis> = {
  60: {
    id: 60, match_id: 'test', move_number: 60, player: 'B', move: 'D4',
    winrate: 0.3, score_lead: -5, visits: 1000, top_moves: [],
    grade: 'mistake', points_lost: 4, is_top_move: false,
    is_brilliant: false, is_mistake: true, is_questionable: false,
  },
};

const props = { analysis, totalMoves: 100, onMoveClick: vi.fn(), trend: <div>走势内容</div> };
const expandLabel = '放大当前分析图表或推荐列表';
const collapseLabel = '收起分析工作区';

describe('MoveGradePanel shared workspace', () => {
  it('keeps the five existing tabs and starts on trend without recommendation', () => {
    render(<MoveGradePanel {...props} />);
    expect(screen.getByTestId('grade-panel')).toHaveAttribute('data-tab', 'trend');
    expect(screen.getByText('走势内容')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '推荐', exact: true })).not.toBeInTheDocument();
    for (const name of ['走势', '妙手', '失误', '发挥水准', 'AI吻合度']) {
      expect(screen.getByRole('button', { name, exact: true })).toBeInTheDocument();
    }
    expect(screen.getAllByRole('button', { name: / · 说明$/ })).toHaveLength(1);
  });

  it('starts on recommendation and moves the same mounted child into and out of the rail dialog', () => {
    const mounts = vi.fn();
    const unmounts = vi.fn();
    function Recommendation() {
      const [value, setValue] = useState(0);
      useEffect(() => { mounts(); return unmounts; }, []);
      return <button onClick={() => setValue(value + 1)}>候选 {value}</button>;
    }
    render(<StrictMode><div className="kiosk-rail report-analysis-rail report-rail-v2">
      <MoveGradePanel {...props} recommendation={<Recommendation />} />
    </div></StrictMode>);
    const panel = screen.getByTestId('grade-panel');
    expect(panel).toHaveAttribute('data-tab', 'recommend');
    fireEvent.click(screen.getByRole('button', { name: '候选 0' }));
    const initialMounts = mounts.mock.calls.length;
    const initialUnmounts = unmounts.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: expandLabel }));
    const dialog = screen.getByRole('dialog', { name: '推荐' });
    expect(within(dialog).getByTestId('grade-panel')).toBe(panel);
    expect(screen.getAllByTestId('grade-panel')).toHaveLength(1);
    expect(within(dialog).getByRole('button', { name: '候选 1' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '候选 1' }));
    fireEvent.click(screen.getByRole('button', { name: collapseLabel }));
    expect(screen.queryByRole('dialog', { name: '推荐' })).not.toBeInTheDocument();
    expect(screen.getByTestId('grade-panel')).toBe(panel);
    expect(screen.getByRole('button', { name: '候选 2' })).toBeInTheDocument();
    expect(mounts).toHaveBeenCalledTimes(initialMounts);
    expect(unmounts).toHaveBeenCalledTimes(initialUnmounts);
  });

  it('preserves the active chart, filters and picked move through expand and Escape', () => {
    const onMoveClick = vi.fn();
    render(<MoveGradePanel {...props} onMoveClick={onMoveClick} recommendation={<div>推荐内容</div>} />);
    fireEvent.click(screen.getByRole('button', { name: '失误', exact: true }));
    fireEvent.click(screen.getByRole('button', { name: '中盘', exact: true }));
    fireEvent.click(screen.getByRole('button', { name: '黑方', exact: true }));
    fireEvent.click(screen.getByTestId('grade-lollipop').querySelector('g')!);
    expect(onMoveClick).toHaveBeenCalledWith(60);
    const plot = screen.getByTestId('grade-lollipop');
    const picked = screen.getByTestId('grade-selline');

    fireEvent.click(screen.getByRole('button', { name: expandLabel }));
    expect(within(screen.getByRole('dialog', { name: '失误' })).getByTestId('grade-lollipop')).toBe(plot);
    expect(screen.getByTestId('grade-panel')).toHaveAttribute('data-tab', 'mistake');
    expect(screen.getByRole('button', { name: '中盘', exact: true })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '黑方', exact: true })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByTestId('grade-lollipop')).toBe(plot);
    expect(screen.getByTestId('grade-selline')).toBe(picked);
    fireEvent.keyDown(screen.getByRole('button', { name: collapseLabel }), { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: '失误' })).not.toBeInTheDocument();
    expect(screen.getByTestId('grade-lollipop')).toBe(plot);
    expect(screen.getByTestId('grade-selline')).toHaveTextContent('第 60 手');
  });

  it('keeps the match view across expansion and shows help only beside the active tab', () => {
    render(<MoveGradePanel {...props} recommendation={<div>推荐内容</div>} />);
    fireEvent.click(screen.getByRole('button', { name: '推荐 · 说明' }));
    expect(screen.getByRole('dialog', { name: '推荐 · 说明' })).toHaveTextContent('不是人类落子的概率');
    fireEvent.click(within(screen.getByRole('dialog', { name: '推荐 · 说明' })).getByRole('button', { name: '关闭' }));
    fireEvent.click(screen.getByRole('button', { name: 'AI吻合度', exact: true }));
    fireEvent.click(screen.getByRole('button', { name: '分布', exact: true }));
    fireEvent.click(screen.getByRole('button', { name: expandLabel }));
    expect(screen.getByTestId('grade-match-dist')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '分布', exact: true })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getAllByRole('button', { name: / · 说明$/ })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'AI吻合度 · 说明' }));
    const help = screen.getByRole('dialog', { name: 'AI吻合度 · 说明' });
    expect(help).toHaveTextContent('不能单独当作棋力或作弊的证据');
    fireEvent.keyDown(help, { key: 'Escape' });
    expect(screen.getByRole('dialog', { name: 'AI吻合度' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: collapseLabel }));
    expect(screen.getByTestId('grade-match-dist')).toBeInTheDocument();
  });
});
