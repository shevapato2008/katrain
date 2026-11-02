import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import KifuPage from './KifuPage';
const fixture = vi.hoisted(() => ({ auth: { isLoading: true, isGuest: false, identityKey: null as string | null, token: null as string | null, status: 'checking' }, list: vi.fn(), navigate: vi.fn() }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => fixture.auth }));
vi.mock('../../hooks/useTranslation', () => ({ useTranslation: () => ({ lang: 'cn', t: (_key: string, fallback: string) => fallback }) }));
vi.mock('../../api/kifuApi', () => ({ KifuAPI: { getAlbums: () => Promise.resolve({ items: [], total: 0 }) } }));
vi.mock('../../api/baipuHistoryApi', () => ({ BaipuHistoryAPI: { list: fixture.list } }));
vi.mock('react-router-dom', async original => ({ ...await original<object>(), useNavigate: () => fixture.navigate }));
const record = { id: 'a'.repeat(64), source_id: 'kifu_1', name: '账户棋谱', k: 1, total: 3, completed: false, updated_at: '2026-11-03T01:00:00Z', authority: 'cloud', sync_state: 'synced' };
const page = () => <MemoryRouter><KifuPage /></MemoryRouter>;
beforeEach(() => { vi.clearAllMocks(); Object.assign(fixture.auth, { isLoading: true, isGuest: false, identityKey: null, token: null, status: 'checking' }); fixture.list.mockResolvedValue({ items: [], authority: 'cloud' }); });
it('waits for resolved identity and keeps loading distinct from empty history', async () => {
  const view = render(page()); fireEvent.click(screen.getByRole('button', { name: '最近摆过' }));
  expect(screen.queryByTestId('kifu-recent-empty')).toBeNull();
  expect(screen.getByTestId('kifu-history-loading')).toBeInTheDocument();
  expect(screen.queryByText('账户云端记录')).toBeNull();
  expect(fixture.list).not.toHaveBeenCalled();
  Object.assign(fixture.auth, { isLoading: false, identityKey: 'owner-a', status: 'authenticated' }); view.rerender(page());
  expect(await screen.findByTestId('kifu-recent-empty')).toBeInTheDocument(); expect(fixture.list).toHaveBeenCalled();
});
it('loads account history without browser cache and resumes by durable URL', async () => {
  Object.assign(fixture.auth, { isLoading: false, identityKey: 'owner-a', status: 'authenticated' });
  fixture.list.mockResolvedValue({ items: [record], authority: 'cloud' });
  render(page()); fireEvent.click(screen.getByRole('button', { name: '最近摆过' }));
  await screen.findByText('账户棋谱'); fireEvent.click(screen.getByRole('button', { name: '接着摆' }));
  expect(fixture.navigate).toHaveBeenCalledWith(`/kiosk/baipu/session/history_${record.id}?history=${record.id}`, expect.anything());
});
it('shows unavailable history as an error and hides old owner responses', async () => {
  Object.assign(fixture.auth, { isLoading: false, identityKey: 'owner-a', status: 'authenticated' });
  let finish!: (value: unknown) => void;
  fixture.list.mockReturnValueOnce(new Promise(resolve => { finish = resolve; }));
  const view = render(page()); fireEvent.click(screen.getByRole('button', { name: '最近摆过' }));
  fixture.list.mockRejectedValue(new Error('offline')); fixture.auth.identityKey = 'owner-b'; view.rerender(page());
  expect(await screen.findByTestId('kifu-history-error')).toBeInTheDocument();
  await act(async () => finish({ items: [record], authority: 'cloud' }));
  expect(screen.queryByText('账户棋谱')).toBeNull(); expect(screen.queryByTestId('kifu-recent-empty')).toBeNull();
});
it('labels an empty local cache honestly and refreshes when returning to recent', async () => {
  Object.assign(fixture.auth, { isLoading: false, identityKey: 'owner-a', status: 'authenticated' });
  fixture.list.mockResolvedValue({ items: [], authority: 'local_cache' });
  render(page()); fireEvent.click(screen.getByRole('button', { name: '最近摆过' }));
  expect(await screen.findByText('此设备还没有缓存的账户记录')).toBeInTheDocument();
  const calls = fixture.list.mock.calls.length;
  fireEvent.click(screen.getByRole('button', { name: '名局棋谱' }));
  fireEvent.click(screen.getByRole('button', { name: '最近摆过' }));
  expect(fixture.list.mock.calls.length).toBeGreaterThan(calls);
});
it('keeps completed records and pending/conflict/refused states visible in the existing rows', async () => {
  Object.assign(fixture.auth, { isLoading: false, identityKey: 'owner-a', status: 'authenticated' });
  fixture.list.mockResolvedValue({ items: [
    { ...record, id: 'b'.repeat(64), name: '已完成棋谱', k: 3, completed: true, sync_state: 'pending' },
    { ...record, id: 'c'.repeat(64), name: '冲突棋谱', sync_state: 'conflict' },
    { ...record, id: 'd'.repeat(64), name: '拒绝棋谱', sync_state: 'refused' },
  ], authority: 'local_cache' });
  render(page()); fireEvent.click(screen.getByRole('button', { name: '最近摆过' }));
  expect(await screen.findByText('已摆完')).toBeInTheDocument();
  expect(screen.getByText(/已保存到本机，等待同步/)).toBeInTheDocument();
  expect(screen.getByText(/进度冲突，请选择保留哪份/)).toBeInTheDocument();
  expect(screen.getByText(/本机已保存，同步被拒绝/)).toBeInTheDocument();
});
