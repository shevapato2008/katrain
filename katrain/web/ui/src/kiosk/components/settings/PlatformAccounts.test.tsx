import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import PlatformAccounts from './PlatformAccounts';

const { platformStatus, platformLogout, navigate } = vi.hoisted(() => ({
  platformStatus: vi.fn(), platformLogout: vi.fn(), navigate: vi.fn(),
}));
vi.mock('../../../api', () => ({ API: { platformStatus, platformLogout } }));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => ({ token: null, isAuthenticated: true }) }));
vi.mock('react-router-dom', async (importOriginal) => ({
  ...(await importOriginal<typeof import('react-router-dom')>()),
  useNavigate: () => navigate,
}));

const status = (ogsConnected = true) => ({ platforms: [
  { platform: 'ogs', connected: ogsConnected, saved_username: ogsConnected ? 'alice' : null },
  { platform: 'golaxy', connected: true, saved_username: '13800000000' },
] });
const savedOffline = () => ({ platforms: [
  { platform: 'ogs', connected: false, saved_username: 'alice' },
  { platform: 'golaxy', connected: true, saved_username: '13800000000' },
] });

const renderPage = () => render(<MemoryRouter><PlatformAccounts /></MemoryRouter>);

beforeEach(() => {
  vi.resetAllMocks();
  platformStatus.mockResolvedValue(status());
  platformLogout.mockResolvedValue({});
});

describe('Settings platform accounts', () => {
  it('shows real connected accounts and routes connection through Play', async () => {
    renderPage();
    expect(await screen.findByTestId('platform-account-ogs')).toHaveTextContent('alice');
    expect(screen.getByTestId('platform-account-golaxy')).toHaveTextContent('13800000000');
    fireEvent.click(screen.getByRole('button', { name: '去连接' }));
    expect(navigate).toHaveBeenCalledWith('/kiosk/play');
  });

  it('cancel leaves both accounts connected and sends no logout', async () => {
    renderPage();
    fireEvent.click(within(await screen.findByTestId('platform-account-ogs')).getByRole('button', { name: '登出' }));
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveTextContent('断开 OGS？');
    fireEvent.click(within(dialog).getByRole('button', { name: '取消' }));
    expect(platformLogout).not.toHaveBeenCalled();
    expect(screen.getByTestId('platform-account-ogs')).toHaveTextContent('已连接');
  });

  it('confirm disconnects only the selected account after server confirmation', async () => {
    platformStatus.mockResolvedValueOnce(status()).mockResolvedValueOnce(status(false));
    renderPage();
    fireEvent.click(within(await screen.findByTestId('platform-account-ogs')).getByRole('button', { name: '登出' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '登出' }));
    await waitFor(() => expect(platformLogout).toHaveBeenCalledWith('ogs', null));
    await waitFor(() => expect(screen.getByTestId('platform-account-ogs')).toHaveTextContent('未连接'));
    expect(screen.getByTestId('platform-account-golaxy')).toHaveTextContent('已连接');
  });

  it('logout failure leaves connected state and reports the failure', async () => {
    platformLogout.mockRejectedValue(new Error('network failed'));
    renderPage();
    fireEvent.click(within(await screen.findByTestId('platform-account-ogs')).getByRole('button', { name: '登出' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '登出' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('network failed');
    expect(screen.getByTestId('platform-account-ogs')).toHaveTextContent('已连接');
  });

  it('shows a saved but offline account and lets its owner delete the saved credentials', async () => {
    platformStatus.mockResolvedValueOnce(savedOffline()).mockResolvedValueOnce({ platforms: [
      { platform: 'ogs', connected: false, saved_username: null },
      { platform: 'golaxy', connected: true, saved_username: '13800000000' },
    ] });
    renderPage();
    const ogs = await screen.findByTestId('platform-account-ogs');
    expect(ogs).toHaveTextContent('账号已保存 · 当前未连接 · alice');
    fireEvent.click(within(ogs).getByRole('button', { name: '删除账号' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除账号' }));
    await waitFor(() => expect(platformLogout).toHaveBeenCalledWith('ogs', null));
    await waitFor(() => expect(screen.getByTestId('platform-account-ogs')).toHaveTextContent('未连接'));
    expect(screen.getByTestId('platform-account-ogs')).not.toHaveTextContent('alice');
  });

  it('keeps a saved offline Fox account visible so its credentials can be deleted', async () => {
    platformStatus.mockResolvedValueOnce({ platforms: [
      { platform: 'fox', connected: false, saved_username: 'old_fox_account' },
    ] }).mockResolvedValueOnce({ platforms: [
      { platform: 'fox', connected: false, saved_username: null },
    ] });
    renderPage();
    const fox = await screen.findByTestId('platform-account-fox');
    expect(fox).toHaveTextContent('账号已保存 · 当前未连接 · old_fox_account');
    fireEvent.click(within(fox).getByRole('button', { name: '删除账号' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除账号' }));
    await waitFor(() => expect(platformLogout).toHaveBeenCalledWith('fox', null));
  });

  it('clears only the target locally when DELETE succeeds but status refresh fails', async () => {
    platformStatus.mockResolvedValueOnce(status()).mockRejectedValueOnce(new Error('status network failed'));
    renderPage();
    await waitFor(() => expect(screen.getByTestId('platform-account-ogs')).toHaveTextContent('已连接'));
    fireEvent.click(within(screen.getByTestId('platform-account-ogs')).getByRole('button', { name: '登出' }));
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '登出' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('账号已删除，但没能刷新平台状态');
    expect(screen.getByTestId('platform-account-ogs')).toHaveTextContent('未连接');
    expect(screen.getByTestId('platform-account-ogs')).not.toHaveTextContent('alice');
    expect(screen.getByTestId('platform-account-golaxy')).toHaveTextContent('已连接');
  });
});
