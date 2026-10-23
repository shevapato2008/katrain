import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { OgsStep } from '../../types/ogsCourse';
import { createOgsExercise } from './ogsExercise';
import { OgsCourseBoard } from './OgsCourseBoard';

const rectangularStep: OgsStep = {
  book_id: 1, figure_id: 1, source_id: 'source:1', source_url: '', lesson_id: 'lesson', page: 1, step: 1,
  size: 19, initial_player: 'W', stones: { B: [[9, 4]], W: [[10, 5]] },
  viewport: { col: 0, row: 0, cols: 19, rows: 10 }, letters: { '9,4': 'A' }, shapes: {},
  exercise: { kind: 'puzzle', tree: { point: null, correct: false, wrong: false, children: [{ point: [8, 3], correct: true, wrong: false, children: [] }] } },
  locale: { requested: 'zh-cn', effective: 'zh-cn', text: { title: '局部棋盘', instruction: '白先' } },
  screenshot: null, screenshot_status: 'pending',
};

describe('OGS board crop', () => {
  it('keeps square cells and stones for a source 19×10 viewport', () => {
    render(<OgsCourseBoard step={rectangularStep} state={createOgsExercise(rectangularStep)} onPoint={vi.fn()} />);
    const board = screen.getByTestId('ogs-board');
    const svg = screen.getByRole('img', { name: '19 路互动棋盘' });
    expect(board).toHaveAttribute('data-window', '19x10');
    expect(svg).toHaveAttribute('viewBox', '0 0 1900 1000');
    expect(svg).not.toHaveAttribute('preserveAspectRatio', 'none');
    expect(board.style.getPropertyValue('--ogs-board-width')).toBe('414px');
    expect(board.style.getPropertyValue('--ogs-board-height')).toBe(`${414 * 10 / 19}px`);
    expect(screen.getByTestId('ogs-point-8-3')).toBeInTheDocument();
  });
});
