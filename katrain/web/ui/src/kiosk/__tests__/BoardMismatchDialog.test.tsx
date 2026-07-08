import { render, screen, fireEvent } from '@testing-library/react';
import BoardMismatchDialog from '../components/physical/BoardMismatchDialog';

const base = { open: true, boardSize: 19, onAdoptObserved: vi.fn(), onRestored: vi.fn(), onDismiss: vi.fn() };

it('lists extra and missing stones with GTP labels', () => {
  render(<BoardMismatchDialog {...base} positions={[[15, 15, 1]]} missing={[[3, 3, 2]]} playerToMove="B" />);
  expect(screen.getByText('黑 Q4')).toBeTruthy();   // row15,col15 -> Q4
  expect(screen.getByText('白 D16')).toBeTruthy();  // row3,col3  -> D16
});

it('adopt button only for a single same-color extra stone', () => {
  const onAdopt = vi.fn();
  render(<BoardMismatchDialog {...base} onAdoptObserved={onAdopt} positions={[[15, 15, 1]]} missing={[]} playerToMove="B" />);
  fireEvent.click(screen.getByText('采纳为我的落子'));
  expect(onAdopt).toHaveBeenCalledWith(15, 3);       // x=col=15, y=18-15=3
});
