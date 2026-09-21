import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const navigate = vi.fn();
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

import { useBackTo } from './useBackTo';

const at = (state: unknown) => ({ children }: { children: ReactNode }) => (
  <MemoryRouter initialEntries={[{ pathname: '/kiosk/play/ai/game/s1', state }]}>{children}</MemoryRouter>
);

describe('useBackTo', () => {
  beforeEach(() => navigate.mockReset());

  it('去打开这一屏的那一页写明的地方(开局设置 → 对局前的标定台 → 返回开局设置)', () => {
    const { result } = renderHook(() => useBackTo('/kiosk/play'), {
      wrapper: at({ backTo: '/kiosk/play/ai/setup/free' }),
    });
    act(() => result.current());
    expect(navigate).toHaveBeenCalledWith('/kiosk/play/ai/setup/free');
  });

  it('没写明(继续上一局进来的)⇒ 本模块首页,不按浏览器历史后退', () => {
    const { result } = renderHook(() => useBackTo('/kiosk/play'), { wrapper: at(null) });
    act(() => result.current());
    expect(navigate).toHaveBeenCalledWith('/kiosk/play');
    expect(navigate).not.toHaveBeenCalledWith(-1);
  });
});
