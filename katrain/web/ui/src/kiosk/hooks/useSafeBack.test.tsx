import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

import { useSafeBack } from './useSafeBack';

const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter>{children}</MemoryRouter>;
/** `idx` 是 React Router 写进 `window.history.state` 的本 app 历史序号,0 = 从启动器进来的第一条。 */
const setIdx = (idx: number) => window.history.replaceState({ idx }, '');

describe('useSafeBack', () => {
  beforeEach(() => navigate.mockReset());

  it('板子卡住时排队的 3 下点击只退一步(实测:连退 4 步退出 katrain)', () => {
    setIdx(2);
    const { result } = renderHook(() => useSafeBack('/kiosk/play'), { wrapper });
    act(() => { result.current(); result.current(); result.current(); });
    expect(navigate).toHaveBeenCalledTimes(1);
    expect(navigate).toHaveBeenCalledWith(-1);
  });

  it('已经在本 app 第一条历史上 ⇒ 不再后退(会退回启动器/别家 app),去本模块首页', () => {
    setIdx(0);
    const { result } = renderHook(() => useSafeBack('/kiosk/play'), { wrapper });
    act(() => result.current());
    expect(navigate).toHaveBeenCalledWith('/kiosk/play', { replace: true });
  });
});
