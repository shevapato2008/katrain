import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthProvider, useAuth } from '../../context/AuthContext';
import LoginMethods from './LoginMethods';

vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); localStorage.clear(); });

it.each(['guest', 'signed-out'])('does not report a late password candidate as success after an external logout and clears private fields (%s)', async initial => {
  localStorage.clear();
  let auth!: ReturnType<typeof useAuth>;
  let releaseLogin!: (response: Response) => void;
  const response = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL) => {
    if (String(input).endsWith('/auth/login')) return new Promise<Response>(resolve => { releaseLogin = resolve; });
    if (String(input).endsWith('/auth/logout')) return Promise.resolve(response({}));
    return Promise.resolve(initial === 'guest'
      ? response({ id: 0, uuid: 'review-guest', username: 'guest', rank: '', credits: 0 })
      : { ok: false, status: 401, json: async () => ({}) } as Response);
  }));
  function ObserveAuth() { auth = useAuth(); return null; }
  const done = vi.fn();
  render(<AuthProvider><ObserveAuth /><LoginMethods onSuccess={done} /></AuthProvider>);
  await waitFor(() => expect(auth.isLoading).toBe(false));
  fireEvent.click(screen.getByRole('tab', { name: '账号密码' }));
  fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'review-old-account' } });
  fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'review-private-password' } });
  fireEvent.click(screen.getByRole('button', { name: '登录' }));
  await waitFor(() => expect(releaseLogin).toBeDefined());
  await act(async () => { await auth.logout(); });
  await act(async () => { releaseLogin(response({ access_token: 'review-late-candidate' })); });
  expect({
    successCalls: done.mock.calls.length,
    username: (screen.getByLabelText('用户名') as HTMLInputElement).value,
    password: (screen.getByLabelText('密码') as HTMLInputElement).value,
    token: localStorage.getItem('token'),
  }).toEqual({ successCalls: 0, username: '', password: '', token: null });
});

it.each(['password', 'phone'])('reports a canonical installed %s login as success exactly once', async method => {
  const canonical = { id: 1, uuid: 'review-canonical', username: 'u_canonical', rank: '', credits: 0 };
  const response = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
  vi.stubGlobal('fetch', vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith('/phone/challenges')) return Promise.resolve(response({ challenge_id: 'review-challenge', retry_after: 60, expires_in: 300, delivery: 'sent' }));
    if (path.endsWith('/auth/login') || path.endsWith('/phone/login')) return Promise.resolve(response({ access_token: 'review-installed-token', token_type: 'bearer' }));
    return Promise.resolve((init?.headers as Record<string, string> | undefined)?.Authorization
      ? response(canonical) : { ok: false, status: 401, json: async () => ({}) } as Response);
  }));
  let auth!: ReturnType<typeof useAuth>;
  function ObserveAuth() { auth = useAuth(); return null; }
  const done = vi.fn();
  render(<AuthProvider><ObserveAuth /><LoginMethods onSuccess={done} /></AuthProvider>);
  await waitFor(() => expect(auth.isLoading).toBe(false));
  if (method === 'password') {
    fireEvent.click(screen.getByRole('tab', { name: '账号密码' }));
    fireEvent.change(screen.getByLabelText('用户名'), { target: { value: 'existing-account' } });
    fireEvent.change(screen.getByLabelText('密码'), { target: { value: 'private-password' } });
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
  } else {
    fireEvent.change(screen.getByLabelText('手机号（中国大陆 +86）'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await screen.findByText(/验证码已请求/);
    fireEvent.change(screen.getByLabelText('短信验证码'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: '验证并登录' }));
  }
  await waitFor(() => expect(done).toHaveBeenCalledTimes(1));
  expect(auth.user?.username).toBe('u_canonical');
  expect(localStorage.getItem('token')).toBe('review-installed-token');
});
