import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { API, ApiError } from '../../api';
import LoginMethods from './LoginMethods';

const auth = { login: vi.fn(), loginPhone: vi.fn(), continuePhone: vi.fn(), registerPhone: vi.fn(), identityKey: null as string | null };
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
const challenge = { challenge_id: 'private-challenge', retry_after: 60, expires_in: 300, delivery: 'sent' as const };
beforeEach(() => {
  vi.restoreAllMocks(); Object.values(auth).forEach(value => { if (typeof value === 'function') value.mockReset(); }); auth.identityKey = null;
  auth.loginPhone.mockRejectedValue(new ApiError(409, 'safe', { code: 'profile_required', mode: 'register' }));
  auth.continuePhone.mockResolvedValue({ signup_grant_credits: 0 });
  vi.spyOn(API, 'createPhoneChallenge').mockResolvedValue(challenge);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });
const next = () => fireEvent.click(screen.getByRole('button', { name: 'Continue' }));
const verify = async () => {
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
  fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
  await waitFor(() => expect(screen.getByRole('button', { name: /60/ })).toBeDisabled());
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } }); next();
  await screen.findByLabelText('用户名');
};

it('starts with phone and code, keeps Galaxy without a guest entry and Kiosk with its guest action', () => {
  const view = render(<LoginMethods onSuccess={() => {}} />);
  expect(screen.queryByLabelText('用户名')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('密码')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '注册账号' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '访客登录' })).not.toBeInTheDocument();
  view.rerender(<LoginMethods surface="kiosk" onGuest={() => {}} onSuccess={() => {}} />);
  expect(screen.getByRole('button', { name: '访客登录' })).toBeInTheDocument();
});

it.each(['register', 'complete'])('preserves the proof in the same window for profile_required %s without asking for a new password', async mode => {
  auth.loginPhone.mockRejectedValue(new ApiError(409, 'safe', { code: 'profile_required', mode }));
  const done = vi.fn(); render(<LoginMethods onSuccess={done} />); await verify();
  expect(screen.queryByLabelText('验证码')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('手机号')).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/密码/)).not.toBeInTheDocument();
  expect(screen.getByText(/138.*8000/)).toBeInTheDocument();
  expect(screen.queryByRole('tab')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: '棋手𠮷' } }); next();
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(auth.continuePhone.mock.calls[0][0]).toEqual({ ...auth.loginPhone.mock.calls[0][0], public_username: '棋手𠮷' });
  expect(API.createPhoneChallenge).toHaveBeenCalledTimes(1);
  expect(auth.registerPhone).not.toHaveBeenCalled();
});

it('reveals the original password only after the server requires it, retains the proof and clears the password when name changes', async () => {
  auth.continuePhone.mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'account_password_required' }));
  const done = vi.fn(); render(<LoginMethods onSuccess={done} />); await verify();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'old.player' } }); next();
  const password = await screen.findByLabelText('Original password');
  expect(password).toHaveAttribute('autocomplete', 'current-password');
  fireEvent.change(password, { target: { value: 'private old password' } });
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'new-player' } });
  expect(screen.queryByLabelText('Original password')).not.toBeInTheDocument();
  next(); await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(auth.continuePhone.mock.calls[1][0]).toEqual({ ...auth.loginPhone.mock.calls[0][0], public_username: 'new-player' });
  expect(API.createPhoneChallenge).toHaveBeenCalledTimes(1);
});

it('submits the unchanged old password and shows a private account conflict only after authentication', async () => {
  auth.continuePhone.mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'account_password_required' }))
    .mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'phone_in_use' }));
  render(<LoginMethods onSuccess={() => {}} />); await verify();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'existing' } }); next();
  fireEvent.change(await screen.findByLabelText('Original password'), { target: { value: '  old private password  ' } }); next();
  expect(await screen.findByRole('alert')).toHaveTextContent('This account is linked to another phone');
  expect(screen.queryByText(/139|137/)).not.toBeInTheDocument();
  expect(auth.continuePhone.mock.calls[1][0]).toEqual({ ...auth.loginPhone.mock.calls[0][0], public_username: 'existing', current_password: '  old private password  ' });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in to original account' }));
  expect(screen.getByLabelText('用户名')).toHaveValue('');
  expect(screen.getByLabelText('密码')).toHaveValue('');
});

it.each(['bind_reauth_failed', 'bind_reauth_locked'])('maps private original-password failure %s and preserves its proof', async code => {
  auth.continuePhone.mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'account_password_required' }))
    .mockRejectedValueOnce(new ApiError(code === 'bind_reauth_locked' ? 429 : 401, 'safe', { code, retry_after: code === 'bind_reauth_locked' ? 45 : undefined }));
  const done = vi.fn(); render(<LoginMethods onSuccess={done} />); await verify();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'existing' } }); next();
  fireEvent.change(await screen.findByLabelText('Original password'), { target: { value: 'incorrect old password' } }); next();
  const message = await screen.findByRole('alert');
  expect(message).toHaveTextContent(code === 'bind_reauth_locked' ? 'Try again in 45 seconds' : 'original account password is incorrect');
  expect(screen.getByLabelText('Original password')).toHaveValue('');
  expect(screen.queryByLabelText('验证码')).not.toBeInTheDocument();
  expect(done).not.toHaveBeenCalled();
  expect(auth.continuePhone.mock.calls[1][0].challenge_id).toBe(auth.continuePhone.mock.calls[0][0].challenge_id);
  expect(API.createPhoneChallenge).toHaveBeenCalledOnce();
});

it('preserves proof after a legacy name collision and accepts another name without requesting the existing account password', async () => {
  auth.continuePhone.mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'public_username_taken' }));
  const done = vi.fn(); render(<LoginMethods onSuccess={done} />); await verify();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'occupied' } }); next();
  expect(await screen.findByRole('alert')).toHaveTextContent('用户名已被使用');
  expect(screen.queryByLabelText('Original password')).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'available' } }); next();
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(auth.continuePhone.mock.calls[1][0].challenge_id).toBe(auth.continuePhone.mock.calls[0][0].challenge_id);
});

it.each([0, 5000])('only announces the authoritative nonzero grant (%s)', async grant => {
  auth.continuePhone.mockResolvedValue({ signup_grant_credits: grant });
  const notice = vi.fn(); const done = vi.fn(); render(<LoginMethods onSuccess={done} onNotice={notice} />); await verify();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: '围棋棋手' } }); next();
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  if (grant) expect(notice).toHaveBeenCalledWith('注册成功，已赠送50积分'); else expect(notice).not.toHaveBeenCalled();
});

it('retires local proof expiry, clears a revealed old password and ignores an aborted late continuation', async () => {
  vi.useFakeTimers();
  let release!: (value: { signup_grant_credits: number }) => void;
  auth.continuePhone.mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'account_password_required' }))
    .mockImplementationOnce(() => new Promise(done => { release = done; }));
  const done = vi.fn(); render(<LoginMethods onSuccess={done} />);
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '获取验证码' })));
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
  await act(async () => next());
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'existing' } });
  await act(async () => next());
  fireEvent.change(screen.getByLabelText('Original password'), { target: { value: 'old private password' } });
  fireEvent.click(screen.getByRole('button', { name: '显示密码' }));
  await act(async () => next());
  const signal = auth.continuePhone.mock.calls[1][1];
  act(() => vi.advanceTimersByTime(300000));
  expect(signal.aborted).toBe(true);
  expect(screen.getByLabelText('验证码')).toHaveValue('');
  expect(screen.queryByLabelText('Original password')).not.toBeInTheDocument();
  expect(screen.queryByDisplayValue('old private password')).not.toBeInTheDocument();
  expect(screen.queryByText(/Verified/)).not.toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Continue' })).toBeDisabled();
  expect(API.createPhoneChallenge).toHaveBeenCalledOnce();
  await act(async () => release({ signup_grant_credits: 5000 }));
  expect(done).not.toHaveBeenCalled();
});

it('retires an invalid server proof and clears the old-password and verified state before retry', async () => {
  auth.continuePhone.mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'account_password_required' }))
    .mockRejectedValueOnce(new ApiError(400, 'safe', { code: 'challenge_invalid' }));
  render(<LoginMethods onSuccess={() => {}} />); await verify();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'existing' } }); next();
  fireEvent.change(await screen.findByLabelText('Original password'), { target: { value: 'old private password' } }); next();
  expect(await screen.findByRole('alert')).toHaveTextContent('验证码已失效');
  expect(auth.continuePhone.mock.calls[1][1].aborted).toBe(true);
  expect(screen.getByLabelText('验证码')).toHaveValue('');
  expect(screen.queryByLabelText('Original password')).not.toBeInTheDocument();
  expect(screen.queryByText(/Verified/)).not.toBeInTheDocument();
  expect(API.createPhoneChallenge).toHaveBeenCalledOnce();
});

it('expires the same-form proof and uses a new code before continuing', async () => {
  vi.useFakeTimers(); render(<LoginMethods onSuccess={() => {}} />);
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '获取验证码' })));
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
  await act(async () => next());
  act(() => vi.advanceTimersByTime(300000));
  expect(screen.getByText('验证码已过期，请重新获取')).toBeInTheDocument();
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '获取验证码' })));
  expect(screen.getByLabelText('验证码')).toHaveValue('');
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'fresh-name' } });
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '654321' } });
  await act(async () => next());
  expect(auth.continuePhone.mock.calls[0][0].code).toBe('654321');
});

it('aborts and clears private continuation when going back or switching identity', async () => {
  let resolve!: (value: { signup_grant_credits: number }) => void;
  auth.continuePhone.mockImplementation(() => new Promise(done => { resolve = done; }));
  const done = vi.fn(); const view = render(<LoginMethods onSuccess={done} />); await verify();
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'private-name' } }); next();
  fireEvent.click(screen.getByRole('button', { name: 'Change phone number' }));
  expect(auth.continuePhone.mock.calls[0][1].aborted).toBe(true);
  expect(screen.getByLabelText('手机号')).toHaveValue('');
  await act(async () => resolve({ signup_grant_credits: 5000 })); expect(done).not.toHaveBeenCalled();
  auth.identityKey = 'different'; view.rerender(<LoginMethods onSuccess={done} />);
  expect(screen.getByLabelText('手机号')).toHaveValue('');
});
