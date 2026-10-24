import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { OgsStep } from '../../types/ogsCourse';
import { createOgsExercise } from './ogsExercise';
import { OgsCourseBoard } from './OgsCourseBoard';

// Pinned OGS export fragment for ogs-learning:bl4-opening-4:1 (page 3006).
const openingStep: OgsStep = {
  book_id: 1, figure_id: 1, source_id: 'ogs-learning:bl4-opening-4:1', source_url: '', lesson_id: 'bl4-opening-4', page: 3006, step: 1,
  size: 19, initial_player: 'W',
  stones: { B: [[15, 15], [15, 16], [16, 12], [2, 16], [3, 15], [3, 13]], W: [[13, 16], [10, 16], [3, 17], [5, 16]] },
  viewport: { col: 0, row: 9, cols: 19, rows: 10 }, letters: { '7,15': 'A', '7,16': 'B', '8,16': 'C' }, shapes: {},
  exercise: { kind: 'puzzle', tree: { point: null, correct: false, wrong: false, children: [{ point: [7, 15], correct: true, wrong: false, children: [] }] } },
  locale: { requested: 'zh-cn', effective: 'zh-cn', text: { title: '布局', instruction: '白先。在A,B,C中选择最佳的防御方法。' } },
  screenshot: null, screenshot_status: 'pending',
};

describe('OGS board crop', () => {
  it('keeps the imported 19×10 crop square and maps A to its absolute board point', () => {
    const onPoint = vi.fn();
    render(<OgsCourseBoard step={openingStep} state={createOgsExercise(openingStep)} onPoint={onPoint} />);
    const board = screen.getByTestId('ogs-board');
    const svg = screen.getByRole('img', { name: '19 路互动棋盘' });
    expect(board).toHaveAttribute('data-window', '19x10');
    expect(svg).toHaveAttribute('viewBox', '0 900 1900 1000');
    expect(svg).not.toHaveAttribute('preserveAspectRatio', 'none');
    expect(board.style.getPropertyValue('--ogs-board-width')).toBe('414px');
    expect(board.style.getPropertyValue('--ogs-board-height')).toBe(`${414 * 10 / 19}px`);
    expect(within(svg).getByText('A')).toBeInTheDocument();
    expect(within(svg).getByText('B')).toBeInTheDocument();
    expect(within(svg).getByText('C')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('ogs-point-7-15'));
    expect(onPoint).toHaveBeenCalledWith([7, 15]);
  });
});
