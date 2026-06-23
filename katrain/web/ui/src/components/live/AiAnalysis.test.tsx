import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { MoveAnalysis } from '../../types/live';
import AiAnalysis from './AiAnalysis';

function move(m: string, pv: string[]) {
  return { move: m, visits: 100, winrate: 0.55, score_lead: 2, prior: 0.5, pv, psv: 100 };
}

const analysis: Record<number, MoveAnalysis> = {
  10: {
    match_id: 'm',
    move_number: 10,
    move: null,
    player: null,
    winrate: 0.55,
    score_lead: 2,
    top_moves: [move('Q16', ['Q16', 'D4']), move('R14', ['R14', 'C3'])],
    ownership: null,
    is_brilliant: false,
    is_mistake: false,
    is_questionable: false,
    delta_score: 0,
    delta_winrate: 0,
  },
};

describe('AiAnalysis — touch onMoveSelect', () => {
  it('calls onMoveSelect with the move key when a row is tapped', () => {
    const onMoveSelect = vi.fn();
    render(<AiAnalysis currentMove={10} analysis={analysis} onMoveSelect={onMoveSelect} activeMove={null} />);
    fireEvent.click(screen.getByText('Q16'));
    expect(onMoveSelect).toHaveBeenCalledWith('Q16');
  });

  it('toggles off (null) when the already-active row is tapped again', () => {
    const onMoveSelect = vi.fn();
    render(<AiAnalysis currentMove={10} analysis={analysis} onMoveSelect={onMoveSelect} activeMove="Q16" />);
    fireEvent.click(screen.getByText('Q16'));
    expect(onMoveSelect).toHaveBeenCalledWith(null);
  });

  it('leaves the Galaxy hover path intact (onMoveHover fires on mouse enter/leave)', () => {
    const onMoveHover = vi.fn();
    render(<AiAnalysis currentMove={10} analysis={analysis} onMoveHover={onMoveHover} />);
    const row = screen.getByText('R14').closest('div')!.parentElement!;
    fireEvent.mouseEnter(row);
    expect(onMoveHover).toHaveBeenCalledWith(['R14', 'C3']);
    fireEvent.mouseLeave(row);
    expect(onMoveHover).toHaveBeenLastCalledWith(null);
  });
});
