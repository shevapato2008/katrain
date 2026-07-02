import { render, screen, fireEvent } from '@testing-library/react';
import HintPanel from '../components/physical/HintPanel';

const moves = [{ gtp: 'Q16', coords: [15, 15] as [number, number], vision_rc: [3, 15] as [number, number], winrate: 0.61, score_lead: 2.3, visits: 100 }];

it('renders winrate/score and closes', () => {
  const onClose = vi.fn();
  render(<HintPanel moves={moves} timeoutS={30} onClose={onClose} />);
  expect(screen.getByText(/Q16/)).toBeTruthy();
  expect(screen.getByText(/61\.0%/)).toBeTruthy();
  fireEvent.click(screen.getByText('关闭'));
  expect(onClose).toHaveBeenCalled();
});
