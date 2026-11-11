import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError } from '../../api';
import PhoneBindDialog from './PhoneBindDialog';

const auth = { user: { username: 'existing-player', is_admin: false }, isGuest: false, isStrictBoxKiosk: false, identityKey: 'account-a', token: 'token-a' };
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
const challenge = { challenge_id: 'bind-challenge', retry_after: 60, expires_in: 300, delivery: 'sent' as const };
beforeEach(() => {
  vi.restoreAllMocks(); auth.identityKey = 'account-a'; auth.token = 'token-a';
  vi.spyOn(API, 'phoneStatus').mockResolvedValue({ bound: false });
  vi.spyOn(API, 'createPhoneBindChallenge').mockResolvedValue(challenge);
  vi.spyOn(API, 'phoneBind').mockResolvedValue({ bound: true, masked_phone: '138****8000' });
});
afterEach(() => { cleanup(); vi.useRealTimers(); });
const ready = async () => { await screen.findByLabelText('手机号（中国大陆 +86）'); };
const getCode = async () => {
  await ready();
  fireEvent.change(screen.getByLabelText('手机号（中国大陆 +86）'), { target: { value: '13800138000' } });
  fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
  await screen.findByText(/验证码已请求/);
  fireEvent.change(screen.getByLabelText('短信验证码'), { target: { value: '123456' } });
  fireEvent.change(screen.getByLabelText('当前账号密码'), { target: { value: 'private-current-password' } });
};

describe('PhoneBindDialog', () => {
  it('binds the verified phone to the captured account, clears secrets and displays only the server mask', async () => {
    const onBound = vi.fn(); render(<PhoneBindDialog open onClose={() => {}} onBound={onBound} />);
    await getCode();
    const request = vi.mocked(API.createPhoneBindChallenge).mock.calls[0][0];
    expect(request).toMatchObject({ phone: '13800138000', purpose: 'bind' });
    expect(request.flow_id).toMatch(/^[a-f0-9]{32}$/);
    expect(API.createPhoneBindChallenge).toHaveBeenCalledWith(request, 'token-a', expect.any(AbortSignal));
    fireEvent.click(screen.getByRole('button', { name: '确认绑定' }));
    expect(await screen.findByText('手机号绑定成功')).toBeInTheDocument();
    expect(API.phoneBind).toHaveBeenCalledWith({ challenge_id: 'bind-challenge', code: '123456', flow_id: request.flow_id, current_password: 'private-current-password' }, 'token-a', expect.any(AbortSignal));
    expect(screen.getByText('138****8000')).toBeInTheDocument();
    expect(screen.queryByLabelText('当前账号密码')).not.toBeInTheDocument();
    expect(onBound).toHaveBeenCalledWith({ bound: true, masked_phone: '138****8000' });
    expect(screen.queryByText(/50/)).not.toBeInTheDocument();
  });
  it('shows an already bound mask without editable binding controls', async () => {
    vi.mocked(API.phoneStatus).mockResolvedValue({ bound: true, masked_phone: '139****9000' });
    render(<PhoneBindDialog open onClose={() => {}} />);
    expect(await screen.findByText('139****9000')).toBeInTheDocument();
    expect(screen.queryByLabelText('手机号（中国大陆 +86）')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '确认绑定' })).not.toBeInTheDocument();
  });
  it.each(['phone_in_use', 'bind_reauth_failed', 'bind_reauth_locked'])('keeps errors honest and permits only eligible retry: %s', async code => {
    vi.mocked(API.phoneBind).mockRejectedValue(new ApiError(code === 'phone_in_use' ? 409 : 429, 'safe', { code, retry_after: code === 'bind_reauth_locked' ? 900 : undefined }));
    render(<PhoneBindDialog open onClose={() => {}} />); await getCode();
    fireEvent.click(screen.getByRole('button', { name: '确认绑定' }));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(code === 'phone_in_use' ? '已绑定其他账号' : code === 'bind_reauth_failed' ? '当前账号密码不正确' : '900秒后再试'));
    expect(screen.getByLabelText('手机号（中国大陆 +86）')).toHaveValue('13800138000');
    if (code === 'bind_reauth_locked') expect(screen.getByRole('button', { name: '确认绑定' })).toBeDisabled();
    expect(screen.queryByText('手机号绑定成功')).not.toBeInTheDocument();
  });
  it('discards late bind results and clears fields when the token changes within an identity', async () => {
    let finish!: (value: { bound: true; masked_phone: string }) => void;
    vi.mocked(API.phoneBind).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const onBound = vi.fn();
    const view = render(<PhoneBindDialog open onClose={() => {}} onBound={onBound} />); await getCode();
    fireEvent.click(screen.getByRole('button', { name: '确认绑定' }));
    auth.token = 'token-b';
    view.rerender(<PhoneBindDialog open onClose={() => {}} onBound={onBound} />);
    expect(vi.mocked(API.phoneBind).mock.calls[0][2]?.aborted).toBe(true);
    await act(async () => finish({ bound: true, masked_phone: '138****8000' }));
    await ready();
    expect(screen.getByLabelText('当前账号密码')).toHaveValue('');
    expect(screen.getByLabelText('手机号（中国大陆 +86）')).toHaveValue('');
    expect(onBound).not.toHaveBeenCalled();
    expect(screen.queryByText('138****8000')).not.toBeInTheDocument();
  });
  it('keeps unknown delivery verifiable and discards a submission after close', async () => {
    vi.mocked(API.createPhoneBindChallenge).mockResolvedValue({ ...challenge, delivery: 'unknown' });
    let finish!: (value: { bound: true; masked_phone: string }) => void;
    vi.mocked(API.phoneBind).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const onBound = vi.fn(); const view = render(<PhoneBindDialog open onClose={() => {}} onBound={onBound} />);
    await ready(); fireEvent.change(screen.getByLabelText('手机号（中国大陆 +86）'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    expect(await screen.findByText(/发送状态未确认/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('短信验证码'), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText('当前账号密码'), { target: { value: 'private-password' } });
    fireEvent.click(screen.getByRole('button', { name: '确认绑定' }));
    view.rerender(<PhoneBindDialog open={false} onClose={() => {}} onBound={onBound} />);
    expect(vi.mocked(API.phoneBind).mock.calls[0][2]?.aborted).toBe(true);
    await act(async () => finish({ bound: true, masked_phone: '138****8000' }));
    expect(onBound).not.toHaveBeenCalled();
    view.rerender(<PhoneBindDialog open onClose={() => {}} onBound={onBound} />); await ready();
    expect(screen.getByLabelText('当前账号密码')).toHaveValue('');
    expect(screen.getByLabelText('手机号（中国大陆 +86）')).toHaveValue('');
  });
  it('requires explicit status retry before rendering a binding form after a load failure', async () => {
    vi.mocked(API.phoneStatus).mockRejectedValueOnce(new Error('offline'));
    render(<PhoneBindDialog open onClose={() => {}} />);
    expect(await screen.findByText('暂时无法读取手机号绑定状态')).toBeInTheDocument();
    expect(screen.queryByLabelText('当前账号密码')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重试' })); await ready();
    expect(API.phoneStatus).toHaveBeenCalledTimes(2);
  });
});
