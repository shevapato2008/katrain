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

describe('AiAnalysis candidate limit', () => {
  const candidates = ['Q16', 'R14', 'D4', 'C3', 'F6', 'K10'];
  const sixCandidateAnalysis = {
    10: { ...analysis[10], top_moves: candidates.map((candidate) => move(candidate, [candidate, 'T19'])) },
  };

  it.each([
    ['default', undefined, 3],
    ['report', 5, 5],
  ])('renders the %s candidate count', (_name, topN, count) => {
    render(<AiAnalysis currentMove={10} analysis={sixCandidateAnalysis} topN={topN} />);

    candidates.forEach((candidate, index) => {
      if (index < count) expect(screen.getByText(candidate)).toBeInTheDocument();
      else expect(screen.queryByText(candidate)).not.toBeInTheDocument();
    });
    expect(sixCandidateAnalysis[10].top_moves).toHaveLength(6);
  });

  it('keeps the sixth actual move available for comparison and PV hover', () => {
    const onMoveHover = vi.fn();
    const withActualMove = {
      ...sixCandidateAnalysis,
      11: { ...analysis[10], move_number: 11, move: 'K10' },
    };
    render(<AiAnalysis currentMove={10} analysis={withActualMove} topN={5} onMoveHover={onMoveHover} />);

    candidates.forEach((candidate) => expect(screen.getByText(candidate)).toBeInTheDocument());
    const row = screen.getByText('K10').closest('div')!.parentElement!;
    fireEvent.mouseEnter(row);
    expect(onMoveHover).toHaveBeenCalledWith(['K10', 'T19']);
    expect(withActualMove[10].top_moves).toHaveLength(6);
  });

  it('keeps report recommendations to five, with a stable top-ten denominator and separate actual move', () => {
    const candidatesWithSixth = candidates.map((candidate, index) => ({ ...move(candidate, [candidate]), psv: index === 5 ? 500 : 100 }));
    const report = {
      10: { ...analysis[10], top_moves: candidatesWithSixth },
      11: { ...analysis[10], move_number: 11, move: 'K10' },
    };
    render(<AiAnalysis currentMove={10} analysis={report} topN={5} reportMode playerToMove="W" />);
    expect(screen.getAllByText('10%')).toHaveLength(5);
    expect(screen.getByTestId('report-actual-move')).toHaveTextContent('K10');
    expect(screen.getByText(/白方待落子/)).toBeInTheDocument();
    expect(report[10].top_moves).toHaveLength(6);
  });

  it('does not invent an evaluation when the played move was outside stored candidates', () => {
    const report = { 10: analysis[10], 11: { ...analysis[10], move_number: 11, move: 'T18' } };
    render(<AiAnalysis currentMove={10} analysis={report} topN={5} reportMode />);
    expect(screen.getByTestId('report-actual-move')).toHaveTextContent('暂无评估');
  });

  it('shows the SGF move when the following position has no analysis row', () => {
    render(<AiAnalysis currentMove={10} analysis={analysis} topN={5} reportMode actualMove="T18" />);
    expect(screen.getByTestId('report-actual-move')).toHaveTextContent('T18');
    expect(screen.getByTestId('report-actual-move')).toHaveTextContent('暂无评估');
  });
});

describe('AiAnalysis — touch onMoveSelect', () => {
  it('exposes touch rows as translated, keyboard-focusable 48px buttons', () => {
    render(<AiAnalysis currentMove={10} analysis={analysis} onMoveSelect={vi.fn()} activeMove={null} />);
    const row = screen.getByRole('button', { name: /Q16/ });
    expect(row).toHaveAttribute('tabindex', '0');
    expect(row).toHaveStyle({ minHeight: '48px' });
  });

  it('calls onMoveSelect with the move key when a row is tapped', () => {
    const onMoveSelect = vi.fn();
    render(<AiAnalysis currentMove={10} analysis={analysis} onMoveSelect={onMoveSelect} activeMove={null} />);
    fireEvent.click(screen.getByText('Q16'));
    expect(onMoveSelect).toHaveBeenCalledWith('Q16');
  });

  it.each(['Enter', ' '])('activates a focused recommendation with the %s key', (key) => {
    const onMoveSelect = vi.fn();
    render(<AiAnalysis currentMove={10} analysis={analysis} onMoveSelect={onMoveSelect} activeMove={null} />);
    fireEvent.keyDown(screen.getByRole('button', { name: /Q16/ }), { key });
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
    expect(row).toHaveStyle({ cursor: 'pointer' });
    fireEvent.mouseEnter(row);
    expect(onMoveHover).toHaveBeenCalledWith(['R14', 'C3']);
    fireEvent.mouseLeave(row);
    expect(onMoveHover).toHaveBeenLastCalledWith(null);
  });

  it('keeps hover-only rows noninteractive to assistive technology and keyboard focus', () => {
    render(<AiAnalysis currentMove={10} analysis={analysis} onMoveHover={vi.fn()} />);
    const row = screen.getByText('Q16').closest('div')!.parentElement!;
    expect(row).not.toHaveAttribute('role');
    expect(row).not.toHaveAttribute('tabindex');
    expect(screen.queryByRole('button', { name: /Q16/ })).not.toBeInTheDocument();
  });

  it('uses the default cursor only when no mouse or touch interaction exists', () => {
    render(<AiAnalysis currentMove={10} analysis={analysis} />);
    const row = screen.getByText('Q16').closest('div')!.parentElement!;
    expect(row).toHaveStyle({ cursor: 'default' });
  });
});
