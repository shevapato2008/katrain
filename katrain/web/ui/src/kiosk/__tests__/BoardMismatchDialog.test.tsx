import { render, screen, fireEvent } from '@testing-library/react';
import BoardMismatchDialog from '../components/physical/BoardMismatchDialog';

const base = { open: true, boardSize: 19, onAdoptObserved: vi.fn(), onRestored: vi.fn(), onNotStone: vi.fn() };

it('lists extra and missing stones with GTP labels', () => {
  render(<BoardMismatchDialog {...base} positions={[[15, 15, 1]]} missing={[[3, 3, 2]]} playerToMove="B" />);
  expect(screen.getByText(/黑 Q4/)).toBeTruthy();   // row15,col15 -> Q4
  expect(screen.getByText(/白 D16/)).toBeTruthy();  // row3,col3  -> D16
});

it('adopt button only for a single same-color extra stone', () => {
  const onAdopt = vi.fn();
  render(<BoardMismatchDialog {...base} onAdoptObserved={onAdopt} positions={[[15, 15, 1]]} missing={[]} playerToMove="B" />);
  fireEvent.click(screen.getByRole('button', { name: /采纳为我的落子/ }));
  expect(onAdopt).toHaveBeenCalledWith(15, 3);       // x=col=15, y=18-15=3
});

it('disables duplicate actions and shows a retryable verification failure', () => {
  const { rerender } = render(<BoardMismatchDialog {...base} positions={[[15, 15, 1]]} missing={[]} playerToMove="B" pending />);
  expect(screen.getByRole('button', { name: '正在核对盘面…' })).toBeDisabled();
  expect(screen.getByRole('button', { name: '不是落子' })).toBeDisabled();
  expect(screen.getByRole('button', { name: /采纳为我的落子/ })).toBeDisabled();
  rerender(<BoardMismatchDialog {...base} positions={[]} missing={[[1, 4, 2]]} playerToMove="B" error="核对失败，请重试" />);
  expect(screen.getByRole('alert')).toHaveTextContent('核对失败，请重试');
  expect(screen.getByRole('button', { name: '重试核对' })).toBeEnabled();
  expect(screen.queryByRole('button', { name: /采纳为我的落子/ })).toBeNull();
});

it('places the recovery error before helper content and the missing point', () => {
  render(<BoardMismatchDialog {...base} positions={[]} missing={[[1, 4, 2]]} playerToMove="B" error="盘面核对失败，请重试" />);
  const alert = screen.getByRole('alert');
  const helper = screen.getByText('请看左侧紫圈标出的交叉点，再核对实体棋盘。');
  const missing = screen.getByText(/白 E18/);
  expect(alert.compareDocumentPosition(helper) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(alert.compareDocumentPosition(missing) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByRole('button', { name: '重试核对' })).toBeEnabled();
});
