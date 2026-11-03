import { stoneSpriteUrl } from '../board/stoneAppearance';
import { render } from '@testing-library/react';
import { expect, it } from 'vitest';
import SGFBoard from './SGFBoard';

const payload = { size: 19, stones: { B: [[3, 3]], W: [[4, 4]] }, labels: { '3,3': '1', '4,4': '2' }, letters: { '5,5': 'A' }, shapes: { '6,6': 'triangle' }, highlights: [[3, 3]] } as const;

it('draws a hollow contrasting last-stone ring while preserving book annotations', () => {
  const { container, rerender } = render(<SGFBoard payload={payload as any} last={[3, 3]} maxMoveStep={1} />);
  const marker = () => container.querySelector('[data-testid="tutorial-last-move"]');
  expect(marker()).toHaveAttribute('stroke', '#fff');
  expect(marker()).toHaveAttribute('fill', 'none');
  expect(container.textContent).toContain('1');
  expect(container.textContent).toContain('A');
  expect(container.querySelectorAll('polygon')).toHaveLength(2);
  rerender(<SGFBoard payload={payload as any} last={[4, 4]} maxMoveStep={2} />);
  expect(marker()).toHaveAttribute('stroke', '#000');
  expect(container.textContent).toContain('2');
  rerender(<SGFBoard payload={payload as any} last={[4, 4]} maxMoveStep={1} />);
  expect(marker()).toBeNull();
  rerender(<SGFBoard payload={payload as any} last={[0, 0]} />);
  expect(marker()).toBeNull();
  rerender(<SGFBoard payload={payload as any} />);
  expect(marker()).toBeNull();
});

it('uses shared stone images with stable absolute coordinates across crops', () => {
  const { container, rerender } = render(<SGFBoard payload={payload as any} />);
  const stone = () => container.querySelector('[data-stone-color="W"]');
  expect(stone()?.tagName.toLowerCase()).toBe('image');
  expect(stone()).toHaveAttribute('href', stoneSpriteUrl('W', 19, 4, 4));
  expect(stone()).toHaveAttribute('width', String(32 * .44 * 2));
  rerender(<SGFBoard payload={{ ...payload, viewport: { col: 3, row: 3, cols: 5, rows: 5 } } as any} />);
  expect(stone()).toHaveAttribute('href', stoneSpriteUrl('W', 19, 4, 4));
});
