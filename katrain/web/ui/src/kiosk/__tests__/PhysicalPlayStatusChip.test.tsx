import { render, screen, act } from '@testing-library/react';
import PhysicalPlayStatusChip from '../components/physical/PhysicalPlayStatusChip';

it('shows on move_pending and hides when the node advances', () => {
  const { rerender } = render(
    <PhysicalPlayStatusChip latestEvent={{ type: 'move_pending', data: { row: 3, col: 3 } }} currentNodeId={1} />
  );
  expect(screen.getByText('确认中…')).toBeTruthy();
  rerender(
    <PhysicalPlayStatusChip latestEvent={{ type: 'move_pending', data: { row: 3, col: 3 } }} currentNodeId={2} />
  );
  expect(screen.queryByText('确认中…')).toBeNull();
});
