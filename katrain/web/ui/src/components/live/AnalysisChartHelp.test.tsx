import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ChartTabHelp } from './AnalysisChartHelp';

afterEach(() => vi.useRealTimers());

it('opens at 550ms or on touch/click and closes on Escape', () => {
  vi.useFakeTimers();
  render(<ChartTabHelp label="失误"><p>图上每方最多画 5 条</p></ChartTabHelp>);
  const button = screen.getByRole('button', { name: '失误 · 说明' });
  expect(button).toHaveStyle({ width: '44px', height: '44px' });
  fireEvent.mouseEnter(button);
  act(() => vi.advanceTimersByTime(549));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  act(() => vi.advanceTimersByTime(1));
  expect(screen.getByRole('dialog')).toHaveTextContent('每方最多画 5 条');
  fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
  act(() => vi.runAllTimers());
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  fireEvent.click(button);
  expect(screen.getByRole('dialog')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '关闭' }));
  act(() => vi.runAllTimers());
  fireEvent.mouseEnter(button);
  fireEvent.mouseLeave(button);
  act(() => vi.advanceTimersByTime(550));
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});
