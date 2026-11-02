import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import PhysicalBoardButton from './PhysicalBoardButton';
const f = vi.hoisted(() => ({ auth: { isLoading: false, isGuest: false, identityKey: 'owner-a' as string | null }, navigate: vi.fn() }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => f.auth }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));
vi.mock('react-router-dom', async original => ({ ...await original<object>(), useNavigate: () => f.navigate }));
const sgf = '(;SZ[19];B[dd])';
beforeEach(() => { vi.clearAllMocks(); Object.assign(f.auth, { isLoading: false, isGuest: false, identityKey: 'owner-a' }); });
const mount = () => render(<MemoryRouter initialEntries={['/kiosk/kifu/1/replay']}><PhysicalBoardButton source="kifu_1" name="Original" sgf={sgf} boardSize={19} /></MemoryRouter>);
it('tags the original SGF with its current identity and preserves its return location', () => {
  mount(); fireEvent.click(screen.getByRole('button', { name: '实体盘' }));
  expect(f.navigate).toHaveBeenCalledWith('/kiosk/baipu/session/kifu_1', { state: expect.objectContaining({ sgf, name: 'Original', baipuIdentity: 'owner-a', backTo: '/kiosk/kifu/1/replay' }) });
});
it('disables entry while identity is unresolved', () => {
  f.auth.isLoading = true; mount(); expect(screen.getByRole('button', { name: '实体盘' })).toBeDisabled();
});
it('tags guest navigation and avoids browser disk writes', () => {
  Object.assign(f.auth, { isGuest: true, identityKey: null }); const disk = vi.spyOn(Storage.prototype, 'setItem');
  mount(); fireEvent.click(screen.getByRole('button', { name: '实体盘' }));
  expect(f.navigate).toHaveBeenCalledWith(expect.anything(), { state: expect.objectContaining({ baipuIdentity: 'guest' }) });
  expect(disk).not.toHaveBeenCalled(); disk.mockRestore();
});
