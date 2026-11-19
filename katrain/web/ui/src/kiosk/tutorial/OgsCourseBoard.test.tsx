import { stoneSpriteUrl } from '../../components/board/stoneAppearance';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { OgsPoint, OgsStep } from '../../types/ogsCourse';
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

type AnnotationFixture = Pick<OgsStep, 'lesson_id' | 'page' | 'step' | 'size' | 'viewport' | 'exercise'> & {
  markers: Array<{ label: string; point: OgsPoint; center: OgsPoint; stone?: 'B' | 'W' }>;
};

const minimalPuzzle: OgsStep['exercise'] = {
  kind: 'puzzle', tree: { point: null, correct: false, wrong: false, children: [] },
};

// Pinned rendering-only fragments from the 2026-11-19 source audit, not answer trees.
const annotationFixtures: AnnotationFixture[] = [
  {
    lesson_id: 'self-capture', page: 7, step: 1, size: 19,
    viewport: { col: 0, row: 0, cols: 19, rows: 19 }, exercise: minimalPuzzle,
    // Native 9×9 coordinates have already been adapted to kiosk19.
    markers: [
      { label: 'A', point: [18, 0], center: [1850, 50] },
      { label: 'B', point: [17, 1], center: [1750, 150] },
      { label: 'C', point: [14, 5], center: [1450, 550] },
    ],
  },
  {
    lesson_id: 'eyes', page: 10, step: 1, size: 9,
    viewport: { col: 0, row: 0, cols: 9, rows: 9 }, exercise: minimalPuzzle,
    markers: [
      { label: 'A', point: [3, 2], center: [350, 250] },
      { label: 'B', point: [4, 8], center: [450, 850] },
    ],
  },
  {
    lesson_id: 'ko', page: 18, step: 5, size: 13,
    viewport: { col: 0, row: 3, cols: 8, rows: 10 }, exercise: minimalPuzzle,
    markers: [{ label: '1', point: [0, 10], center: [50, 1050], stone: 'W' }],
  },
  {
    lesson_id: 'bl3-joseki-1', page: 2017, step: 7, size: 19,
    viewport: { col: 0, row: 8, cols: 11, rows: 11 }, exercise: minimalPuzzle,
    markers: [
      { label: '10', point: [1, 14], center: [150, 1450] },
      { label: '11', point: [1, 16], center: [150, 1650] },
      { label: '12', point: [2, 13], center: [250, 1350] },
    ],
  },
  {
    lesson_id: 'bp-ko', page: 167, step: 1, size: 9,
    viewport: { col: 0, row: 0, cols: 9, rows: 9 },
    exercise: {
      kind: 'choice', choices: [{ value: 'yes', label_key: 'yes' }, { value: 'no', label_key: 'no' }], correct_choice: 'no',
    },
    markers: [{ label: '1', point: [2, 4], center: [250, 450], stone: 'B' }],
  },
];

describe('OGS board crop', () => {
  it('keeps the imported 19×10 crop square and maps A to its absolute board point', () => {
    const onPoint = vi.fn();
    render(<OgsCourseBoard step={openingStep} state={createOgsExercise(openingStep)} onPoint={onPoint} />);
    const board = screen.getByTestId('ogs-board');
    const svg = screen.getByRole('img', { name: '19 路互动棋盘' });
    expect(board).toHaveAttribute('data-window', '19x10');
    expect(svg).toHaveAttribute('viewBox', '0 900 1900 1000');
    const sprites = svg.querySelectorAll('image');
    expect(sprites).toHaveLength(10);
    expect(sprites[0]).toHaveAttribute('href', stoneSpriteUrl('B', 19, 16, 12));
    expect(sprites[0]).toHaveAttribute('width', '78');
    expect([...sprites].every(sprite => !sprite.hasAttribute('transform'))).toBe(true);
    expect(svg).not.toHaveAttribute('preserveAspectRatio', 'none');
    expect(board.style.getPropertyValue('--ogs-board-width')).toBe('414px');
    expect(board.style.getPropertyValue('--ogs-board-height')).toBe(`${414 * 10 / 19}px`);
    for (const [label, x, y] of [['A', 7, 15], ['B', 7, 16], ['C', 8, 16]] as const) {
      const marker = within(svg).getByText(label);
      const hit = screen.getByTestId(`ogs-point-${x}-${y}`);
      expect(marker).toHaveAttribute('x', hit.getAttribute('cx'));
      expect(marker).toHaveAttribute('y', hit.getAttribute('cy'));
      expect(marker).toHaveAttribute('dominant-baseline', 'central');
    }
    fireEvent.click(screen.getByTestId('ogs-point-7-15'));
    expect(onPoint).toHaveBeenCalledWith([7, 15]);
  });
});

describe('OGS annotation alignment', () => {
  it.each(annotationFixtures)('centers source markers for $lesson_id step $step (page $page)', ({ markers, ...fixture }) => {
    const stones: OgsStep['stones'] = { B: [], W: [] };
    for (const marker of markers) {
      if (marker.stone) stones[marker.stone].push(marker.point);
    }
    const step: OgsStep = {
      ...openingStep, ...fixture, figure_id: fixture.page,
      source_id: `ogs-learning:${fixture.lesson_id}:${fixture.step}`,
      stones, letters: Object.fromEntries(markers.map(({ point, label }) => [point.join(','), label])),
    };
    render(<OgsCourseBoard step={step} state={createOgsExercise(step)} onPoint={vi.fn()} />);
    const svg = screen.getByRole('img');
    for (const { label, point: [x, y], center: [cx, cy], stone } of markers) {
      const marker = within(svg).getByText(label);
      expect(marker).toHaveAttribute('x', String(cx));
      expect(marker).toHaveAttribute('y', String(cy));
      expect(marker).toHaveAttribute('dominant-baseline', 'central');
      if (stone) {
        const sprite = svg.querySelector('image')!;
        expect(sprite).toHaveAttribute('href', stoneSpriteUrl(stone, step.size, x, y));
        expect(Number(sprite.getAttribute('x')) + Number(sprite.getAttribute('width')) / 2).toBe(cx);
        expect(Number(sprite.getAttribute('y')) + Number(sprite.getAttribute('height')) / 2).toBe(cy);
        expect(screen.queryByTestId(`ogs-point-${x}-${y}`)).not.toBeInTheDocument();
      } else {
        const hit = screen.getByTestId(`ogs-point-${x}-${y}`);
        expect(marker).toHaveAttribute('x', hit.getAttribute('cx'));
        expect(marker).toHaveAttribute('y', hit.getAttribute('cy'));
      }
    }
  });
});
