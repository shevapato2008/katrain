import { render, screen } from '@testing-library/react';
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

const referenceNotice = '参考尚未更新，继续核对盘面';

it.each(['limited', 'unavailable'] as const)('shows one nonmodal notice for an active bound %s target', (referenceStatus) => {
  render(<PhysicalPlayStatusChip latestEvent={null} currentNodeId={16}
    referenceStatus={referenceStatus} referenceReason="witness_mismatch" referenceTargetActive />);
  expect(screen.getAllByText(referenceNotice)).toHaveLength(1);
  expect(screen.queryByRole('dialog')).toBeNull();
});

it.each(['current', 'pending', undefined] as const)('does not add a notice for %s status', (referenceStatus) => {
  render(<PhysicalPlayStatusChip latestEvent={null} currentNodeId={16}
    referenceStatus={referenceStatus} referenceTargetActive />);
  expect(screen.queryByText(referenceNotice)).toBeNull();
});

it('does not warn before an active physical target is known', () => {
  render(<PhysicalPlayStatusChip latestEvent={null} currentNodeId={null} referenceStatus="unavailable" />);
  expect(screen.queryByText(referenceNotice)).toBeNull();
});

it('lets an existing physical or device reminder suppress the reference notice', () => {
  render(<PhysicalPlayStatusChip latestEvent={null} currentNodeId={16}
    referenceStatus="limited" referenceTargetActive suppressReferenceNotice />);
  expect(screen.queryByText(referenceNotice)).toBeNull();
});

it('keeps move confirmation ahead of the reference notice', () => {
  render(<PhysicalPlayStatusChip latestEvent={{ seq: 1, type: 'move_pending', data: { row: 3, col: 3 } }} currentNodeId={16}
    referenceStatus="limited" referenceTargetActive />);
  expect(screen.getByText('确认中…')).toBeTruthy();
  expect(screen.queryByText(referenceNotice)).toBeNull();
});
