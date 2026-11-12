import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { API, ApiError } from '../../api';
import LoginMethods from './LoginMethods';

const auth = { login: vi.fn(), loginPhone: vi.fn(), registerPhone: vi.fn(), identityKey: null as string | null };
vi.mock('../../context/AuthContext', () => ({ useAuth: () => auth }));
const challenge = { challenge_id: 'private-challenge', retry_after: 60, expires_in: 300, delivery: 'sent' as const };
beforeEach(() => {
  vi.restoreAllMocks(); auth.login.mockReset(); auth.loginPhone.mockReset(); auth.registerPhone.mockReset(); auth.identityKey = null;
  vi.spyOn(API, 'createPhoneChallenge').mockResolvedValue(challenge);
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

const verify = async () => {
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
  fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
  await waitFor(() => expect(screen.getByRole('button', { name: /60/ })).toBeDisabled());
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
};

it('offers four registration fields, no confirmation field or promotional text, and no Galaxy guest button', () => {
  render(<LoginMethods onSuccess={() => {}} />);
  expect(screen.queryByText(/赠|绑定手机号/)).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '访客登录' })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: '注册账号' }));
  expect(screen.getAllByRole('textbox')).toHaveLength(3);
  expect(screen.getByLabelText('密码')).toHaveAttribute('type', 'password');
  expect(screen.getByLabelText('用户名（昵称）')).toBeInTheDocument();
  expect(screen.queryByLabelText(/确认密码/)).not.toBeInTheDocument();
});

it.each([
  ['short', '密码至少15个字符'],
  ['中'.repeat(25), '密码过长，请缩短'],
])('shows concise password guidance for invalid input without technical byte limits', (password, message) => {
  render(<LoginMethods onSuccess={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: '注册账号' }));
  fireEvent.change(screen.getByLabelText('用户名（昵称）'), { target: { value: '围棋棋手' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: '注册并登录' }));
  expect(screen.getByRole('alert')).toHaveTextContent(message);
  expect(screen.getByRole('alert')).not.toHaveTextContent(/72|字节|bytes/i);
  expect(auth.registerPhone).not.toHaveBeenCalled();
});

it.each(['register', 'complete'])('preserves one verified challenge for profile_required %s and only submits public name and password afterwards', async mode => {
  auth.loginPhone.mockRejectedValue(new ApiError(409, 'safe', { code: 'profile_required', mode }));
  auth.registerPhone.mockResolvedValue({ signup_grant_credits: 0 });
  const done = vi.fn();
  render(<LoginMethods onSuccess={done} />);
  await verify();
  fireEvent.click(screen.getByRole('button', { name: '登录' }));
  await screen.findByLabelText('用户名（昵称）');
  expect(screen.queryByLabelText('验证码')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('手机号')).not.toBeInTheDocument();
  expect(screen.getByText(/138.*8000/)).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('用户名（昵称）'), { target: { value: '棋手𠮷' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: '  fifteen chars long  ' } });
  fireEvent.click(screen.getByRole('button', { name: '保存并登录' }));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  const original = auth.loginPhone.mock.calls[0][0];
  expect(auth.registerPhone.mock.calls[0][0]).toEqual({ ...original, public_username: '棋手𠮷', password: '  fifteen chars long  ' });
  expect(API.createPhoneChallenge).toHaveBeenCalledTimes(1);
});

it('requires a fresh code when completion expires and clears the old password when returning to login', async () => {
  vi.useFakeTimers();
  auth.loginPhone.mockRejectedValue(new ApiError(409, 'safe', { code: 'profile_required', mode: 'register' }));
  render(<LoginMethods onSuccess={() => {}} />);
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '获取验证码' })));
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '登录' })));
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'very private password' } });
  act(() => vi.advanceTimersByTime(300000));
  expect(screen.getByText('验证码已过期，请重新获取')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '获取验证码' })).toBeInTheDocument();
  await act(async () => fireEvent.click(screen.getByRole('button', { name: '获取验证码' })));
  expect(screen.getByLabelText('验证码')).toHaveValue('');
  fireEvent.click(screen.getByRole('button', { name: '已有账号？去登录' }));
  expect(screen.getByLabelText('密码')).toHaveValue('');
  expect(auth.registerPhone).not.toHaveBeenCalled();
});

it.each([0, 5000])('announces the signup grant only when the authoritative response is %s', async grant => {
  auth.registerPhone.mockResolvedValue({ signup_grant_credits: grant });
  const notice = vi.fn(); const done = vi.fn();
  render(<LoginMethods onSuccess={done} onNotice={notice} />);
  fireEvent.click(screen.getByRole('button', { name: '注册账号' }));
  fireEvent.change(screen.getByLabelText('用户名（昵称）'), { target: { value: '围棋棋手' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'new private password' } });
  await verify();
  fireEvent.click(screen.getByRole('button', { name: '注册并登录' }));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(notice).toHaveBeenCalledWith(grant === 5000 ? '注册成功，已赠送50积分' : '注册成功');
  expect(auth.loginPhone).not.toHaveBeenCalled();
});

it('keeps the original challenge after a username conflict and allows a corrected public name', async () => {
  auth.registerPhone.mockRejectedValueOnce(new ApiError(409, 'safe', { code: 'public_username_taken' })).mockResolvedValue({ signup_grant_credits: 0 });
  const done = vi.fn();
  render(<LoginMethods onSuccess={done} />);
  fireEvent.click(screen.getByRole('button', { name: '注册账号' }));
  fireEvent.change(screen.getByLabelText('用户名（昵称）'), { target: { value: '围棋棋手' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'new private password' } });
  await verify();
  fireEvent.click(screen.getByRole('button', { name: '注册并登录' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('用户名已被使用');
  fireEvent.change(screen.getByLabelText('用户名（昵称）'), { target: { value: '另一个棋手' } });
  fireEvent.click(screen.getByRole('button', { name: '注册并登录' }));
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(auth.registerPhone.mock.calls[1][0].challenge_id).toBe(auth.registerPhone.mock.calls[0][0].challenge_id);
  expect(API.createPhoneChallenge).toHaveBeenCalledTimes(1);
});
