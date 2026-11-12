import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API, ApiError } from '../../api';
import PhoneOtpForm from './PhoneOtpForm';

const loginPhone = vi.fn();
const auth = { loginPhone, identityKey: null as string | null };
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
const challenge = { challenge_id: 'opaque-challenge', retry_after: 60, expires_in: 300, delivery: 'sent' as const };
beforeEach(() => { vi.restoreAllMocks(); loginPhone.mockReset().mockResolvedValue(undefined); auth.identityKey = null; });
afterEach(() => { cleanup(); vi.useRealTimers(); });
const fillPhone = () => fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });

describe('PhoneOtpForm', () => {
  it('uses a private random flow and one six-digit input, then submits the challenge without the phone', async () => {
    const send = vi.spyOn(API, 'createPhoneChallenge').mockResolvedValue(challenge);
    const done = vi.fn();
    render(<PhoneOtpForm onSuccess={done} />);
    fillPhone();
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    expect(send.mock.calls[0][0]).toMatchObject({ phone: '13800138000', purpose: 'login' });
    const flow = send.mock.calls[0][0].flow_id;
    expect(flow).toMatch(/^[a-f0-9]{32}$/);
    const code = screen.getByLabelText('验证码');
    expect(code).toHaveAttribute('autocomplete', 'one-time-code');
    expect(code).toHaveAttribute('inputmode', 'numeric');
    fireEvent.change(code, { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    await waitFor(() => expect(loginPhone).toHaveBeenCalledWith({ challenge_id: 'opaque-challenge', code: '123456', flow_id: flow }, expect.any(AbortSignal)));
    expect(done).toHaveBeenCalledTimes(1);
  });

  it('keeps unknown delivery usable and holds the resend cooldown without automatically retrying', async () => {
    const send = vi.spyOn(API, 'createPhoneChallenge').mockResolvedValue({ ...challenge, delivery: 'unknown' });
    render(<PhoneOtpForm onSuccess={() => {}} />); fillPhone();
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    expect(await screen.findByText(/发送状态未确认/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /60/ })).toBeDisabled();
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    expect(screen.getByRole('button', { name: '登录' })).toBeEnabled();
    expect(send).toHaveBeenCalledTimes(1);
  });

  it('shows a rejected delivery as an error and preserves editable phone input', async () => {
    vi.spyOn(API, 'createPhoneChallenge').mockRejectedValue(new ApiError(503, 'safe', { code: 'sms_rejected', retry_after: 60 }));
    render(<PhoneOtpForm onSuccess={() => {}} />); fillPhone();
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('短信发送被拒绝');
    expect(screen.getByLabelText('手机号')).toBeEnabled();
    expect(loginPhone).not.toHaveBeenCalled();
  });

  it('discards a challenge returned after the phone changes and rotates the flow', async () => {
    let resolve!: (value: typeof challenge) => void;
    const send = vi.spyOn(API, 'createPhoneChallenge').mockImplementationOnce(() => new Promise(r => { resolve = r; })).mockResolvedValue(challenge);
    render(<PhoneOtpForm onSuccess={() => {}} />); fillPhone();
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    const firstFlow = send.mock.calls[0][0].flow_id;
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13900139000' } });
    await act(async () => resolve(challenge));
    expect(screen.getByLabelText('验证码')).toHaveValue('');
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(send).toHaveBeenCalledTimes(2));
    expect(send.mock.calls[1][0].flow_id).not.toBe(firstFlow);
  });

  it('aborts an in-flight verification when unmounted', async () => {
    vi.spyOn(API, 'createPhoneChallenge').mockResolvedValue(challenge);
    loginPhone.mockImplementation(() => new Promise(() => {}));
    const { unmount } = render(<PhoneOtpForm onSuccess={() => {}} />); fillPhone();
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(screen.getByRole('button', { name: /60/ })).toBeDisabled());
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    unmount();
    expect(loginPhone.mock.calls[0][1].aborted).toBe(true);
  });

  it('expires the challenge after 300 seconds and keeps a lost send response on cooldown', async () => {
    vi.useFakeTimers();
    const send = vi.spyOn(API, 'createPhoneChallenge').mockResolvedValue(challenge);
    render(<PhoneOtpForm onSuccess={() => {}} />); fillPhone();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '获取验证码' })); });
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    expect(screen.getByRole('button', { name: '登录' })).toBeEnabled();
    act(() => vi.advanceTimersByTime(300000));
    expect(screen.getByText('验证码已过期，请重新获取')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '登录' })).toBeDisabled();
    send.mockRejectedValueOnce(new TypeError('Network failure'));
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '获取验证码' })); });
    expect(screen.getByRole('alert')).toHaveTextContent('短信服务暂不可用');
    expect(screen.getByRole('button', { name: /60/ })).toBeDisabled();
    expect(send).toHaveBeenCalledTimes(2);
  });

  it('clears private fields and retires a challenge when the canonical identity changes', async () => {
    let resolve!: (value: typeof challenge) => void;
    const send = vi.spyOn(API, 'createPhoneChallenge').mockImplementation(() => new Promise(r => { resolve = r; }));
    const { rerender } = render(<PhoneOtpForm onSuccess={() => {}} />); fillPhone();
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    auth.identityKey = 'new-identity';
    rerender(<PhoneOtpForm onSuccess={() => {}} />);
    expect(send.mock.calls[0][1]?.aborted).toBe(true);
    await act(async () => resolve(challenge));
    expect(screen.getByLabelText('手机号')).toHaveValue('');
    expect(screen.getByLabelText('验证码')).toHaveValue('');
    expect(loginPhone).not.toHaveBeenCalled();
  });
});
