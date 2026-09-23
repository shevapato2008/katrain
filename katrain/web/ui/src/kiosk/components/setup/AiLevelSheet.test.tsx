import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import AiLevelSheet from './AiLevelSheet';
import type { EngineLevel } from '../../../api';

const mk = (n: number): EngineLevel[] => Array.from({ length: n }, (_, i) => ({
  elo_score: 100 + i * 10, level_name: `${i + 1} 段`, name: `星阵 ${i + 1}`,
  goal_difference: 0, timing: '', display_elo: 400 + i * 50, ref_rank: `业余 ${i + 1}`,
}));

describe('AiLevelSheet', () => {
  it('39 档一个不少', () => {
    render(<AiLevelSheet levels={mk(39)} currentElo={null} onPick={() => {}} onClose={() => {}} testId="sheet" />);
    expect(screen.getAllByTestId('level-row')).toHaveLength(39);
  });

  it('选中的那一行带 aria-current', () => {
    render(<AiLevelSheet levels={mk(39)} currentElo={310} onPick={() => {}} onClose={() => {}} testId="sheet" />);
    const rows = screen.getAllByTestId('level-row');
    expect(within(rows[21]).getByRole('button')).toHaveAttribute('aria-current', 'true');
  });

  it('点一行就回传并关闭', async () => {
    const onPick = vi.fn(); const onClose = vi.fn();
    render(<AiLevelSheet levels={mk(39)} currentElo={100} onPick={onPick} onClose={onClose} testId="sheet" />);
    await userEvent.click(within(screen.getAllByTestId('level-row')[5]).getByRole('button'));
    expect(onPick).toHaveBeenCalledWith(150);
    expect(onClose).toHaveBeenCalledOnce();
  });

  // Review Focus #1:平台只下发 0 档
  it('一档都没有时,面板说明白是平台没给,不画空列表', () => {
    render(<AiLevelSheet levels={[]} currentElo={null} onPick={() => {}} onClose={() => {}} testId="sheet" />);
    expect(screen.queryAllByTestId('level-row')).toHaveLength(0);
    expect(screen.getByTestId('sheet')).toHaveTextContent('没能从平台取回棋力档');
  });
});
