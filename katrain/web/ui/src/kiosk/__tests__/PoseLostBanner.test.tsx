import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PoseLostBanner from '../components/physical/PoseLostBanner';

const calibrate = vi.fn().mockResolvedValue({});
const visionResetSync = vi.fn().mockResolvedValue(undefined);
// Mock paths are resolved relative to THIS test file (src/kiosk/__tests__/), and must
// resolve to the same module the component imports (src/api/geometryApi.ts, src/api.ts).
// __tests__ -> kiosk -> src is two levels up.
vi.mock('../../api/geometryApi', () => ({ GeometryAPI: { calibrate: (...a: unknown[]) => calibrate(...a) } }));
vi.mock('../../api', () => ({ API: { visionResetSync: (...a: unknown[]) => visionResetSync(...a) } }));

beforeEach(() => {
  calibrate.mockClear();
  visionResetSync.mockClear();
});

it('recalibration is user-triggered only, with explicit manual trigger', async () => {
  render(<PoseLostBanner visible />);
  expect(calibrate).not.toHaveBeenCalled(); // 渲染本身绝不触发（D2③）
  fireEvent.click(screen.getByText('重新定位'));
  await waitFor(() => expect(calibrate).toHaveBeenCalledTimes(1));
  expect(calibrate).toHaveBeenCalledWith('manual'); // 评审 Codex I4
});

it('surfaces an error message when calibrate rejects, without calling visionResetSync', async () => {
  calibrate.mockRejectedValueOnce(new Error('busy'));
  render(<PoseLostBanner visible />);
  fireEvent.click(screen.getByText('重新定位'));
  await waitFor(() => expect(calibrate).toHaveBeenCalledTimes(1));
  expect(await screen.findByText('重新定位失败，请重试')).toBeInTheDocument();
  expect(visionResetSync).not.toHaveBeenCalled();
});
