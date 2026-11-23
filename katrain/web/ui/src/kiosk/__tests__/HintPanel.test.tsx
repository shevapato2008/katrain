import { render, screen, fireEvent } from '@testing-library/react';
import HintPanel from '../components/physical/HintPanel';

const moves = [
  { gtp: 'Q16', coords: [15, 15] as [number, number], vision_rc: [3, 15] as [number, number], winrate: 0.61, score_lead: 2.3, visits: 100 },
  { gtp: 'D4', coords: [3, 3] as [number, number], vision_rc: [15, 3] as [number, number], winrate: 0.58, score_lead: 1.9, visits: 80 },
  { gtp: 'C3', coords: [2, 2] as [number, number], vision_rc: [16, 2] as [number, number], winrate: 0.55, score_lead: 1.0, visits: 60 },
];

it('renders Red/Yellow/Green rank badges, winrate/score, and closes', () => {
  const onClose = vi.fn();
  render(<HintPanel moves={moves} timeoutS={30} onClose={onClose} />);
  expect(screen.getByText(/AI 支招（红 \/ 黄 \/ 绿灯闪烁处）/)).toBeTruthy();
  expect(screen.getByTestId('hint-rank-badge-1')).toHaveTextContent('红 · 首选');
  expect(screen.getByTestId('hint-rank-badge-2')).toHaveTextContent('黄 · 次选');
  expect(screen.getByTestId('hint-rank-badge-3')).toHaveTextContent('绿 · 三选');
  expect(screen.getByText(/Q16/)).toBeTruthy();
  expect(screen.getByText(/61\.0%/)).toBeTruthy();
  fireEvent.click(screen.getByText('关闭'));
  expect(onClose).toHaveBeenCalled();
});

it('auto-closes after timeoutS with a stable onClose', () => {
  vi.useFakeTimers();
  try {
    const onClose = vi.fn();
    render(<HintPanel moves={moves} timeoutS={30} onClose={onClose} />);
    expect(onClose).not.toHaveBeenCalled();
    vi.advanceTimersByTime(30000);
    expect(onClose).toHaveBeenCalledTimes(1);
  } finally {
    vi.useRealTimers();
  }
});
