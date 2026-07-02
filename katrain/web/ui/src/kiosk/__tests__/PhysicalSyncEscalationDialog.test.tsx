import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PhysicalSyncEscalationDialog from '../components/physical/PhysicalSyncEscalationDialog';

const resetSync = vi.fn().mockResolvedValue(undefined);
const unbind = vi.fn().mockResolvedValue(undefined);
vi.mock('../../api', () => ({
  API: { visionResetSync: () => resetSync(), visionUnbind: () => unbind() },
}));

const base = { open: true, toPlace: [[3, 3]], toRemove: [], onClose: vi.fn() };

it('restored resets sync; screen-play unbinds vision', async () => {
  const { unmount } = render(<PhysicalSyncEscalationDialog {...base} />);
  fireEvent.click(screen.getByText('已按指示恢复'));
  await waitFor(() => expect(resetSync).toHaveBeenCalledTimes(1));
  // MUI Dialog portals to document.body — unmount the first instance before
  // rendering a second one, otherwise both dialogs' buttons coexist in the DOM.
  unmount();
  render(<PhysicalSyncEscalationDialog {...base} />);
  fireEvent.click(screen.getByText('改用屏幕落子'));
  await waitFor(() => expect(unbind).toHaveBeenCalledTimes(1));
});
