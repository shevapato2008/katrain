import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PoseLostBanner from '../components/physical/PoseLostBanner';

const calibrate = vi.fn().mockResolvedValue({});
// Mock paths are resolved relative to THIS test file (src/kiosk/__tests__/), and must
// resolve to the same module the component imports (src/api/geometryApi.ts, src/api.ts).
// __tests__ -> kiosk -> src is two levels up.
vi.mock('../../api/geometryApi', () => ({ GeometryAPI: { calibrate: (...a: unknown[]) => calibrate(...a) } }));
vi.mock('../../api', () => ({ API: { visionResetSync: vi.fn().mockResolvedValue(undefined) } }));

it('recalibration is user-triggered only, with explicit manual trigger', async () => {
  render(<PoseLostBanner visible />);
  expect(calibrate).not.toHaveBeenCalled(); // 渲染本身绝不触发（D2③）
  fireEvent.click(screen.getByText('重新定位'));
  await waitFor(() => expect(calibrate).toHaveBeenCalledTimes(1));
  expect(calibrate).toHaveBeenCalledWith('manual'); // 评审 Codex I4
});
