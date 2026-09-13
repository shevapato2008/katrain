import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SettingsProvider } from '../../../../context/SettingsContext';
import { API } from '../../../../api';
import BindPhoneDialog from '../BindPhoneDialog';

let authFixture: { token: string; isAuthenticated: boolean;
                   user: { id: number; username: string; phone_bound: boolean } | null;
                   refreshUser: ReturnType<typeof vi.fn> };
function resetAuth(bound = true) {
  authFixture = {
    token: 't', isAuthenticated: true,
    user: { id: 1, username: 'u', phone_bound: bound },
    refreshUser: vi.fn().mockResolvedValue(undefined),
  };
}
resetAuth();
vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

const renderDlg = (purpose: 'bind' | 'set_password') =>
  render(
    <MemoryRouter><SettingsProvider>
      <BindPhoneDialog open purpose={purpose} onClose={() => {}} />
    </SettingsProvider></MemoryRouter>,
  );

afterEach(() => { cleanup(); });

describe('改密码对话框（与绑定共用一个壳，只换 purpose）', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetAuth();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('purpose=set_password 时多一个新密码输入框，绑定模式下没有', () => {
    renderDlg('set_password');
    expect(screen.getByLabelText('新密码')).toBeInTheDocument();
    cleanup();
    renderDlg('bind');
    expect(screen.queryByLabelText('新密码')).toBeNull();
  });

  it('发码时带的 purpose 是 set_password，不是 bind', async () => {
    const spy = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderDlg('set_password');
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(spy).toHaveBeenCalledWith('+8613800138000', 'set_password'));
  });

  it('填了别人的号时说清是「这个号不是你绑的那个」，不是通用失败', async () => {
    /* 计划原稿想把号码框做成只读的掩码。**做不出来**：/auth/me 永不返回手机号、
       连掩码都不给（phone_masked 只在 bind 成功那一次返回一次）。
       后端的真实契约是让用户自己填，服务端再比对：
       auth.py:562 `if phone != repo.get_phone_e164(current_user.id)` → 403 challenge_phone_mismatch。
       所以出路靠这条映射，不靠一个填不出来的只读框。 */
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    vi.spyOn(API, 'setPassword').mockRejectedValue(
      Object.assign(new Error('x'), { code: 'challenge_phone_mismatch', status: 403 }));
    renderDlg('set_password');
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13900139000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'newpw123456' } });
    fireEvent.click(screen.getByRole('button', { name: '确认修改' }));
    await waitFor(() => expect(screen.getByText(/不是这个账号绑定的手机号/)).toBeInTheDocument());
  });

  it('未绑手机的用户拿到的是「先去绑定」，不是一个填不了的表单', () => {
    // 后端 auth.py:548-552 对未绑号的 set-password 直接 400 phone_unbound ——
    // 让他填完一整张表再被拒，是把已知的失败藏到最后一步。
    resetAuth(false);
    renderDlg('set_password');
    expect(screen.getByText(/先绑定手机号/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '获取验证码' })).toBeNull();
    expect(screen.queryByLabelText('新密码')).toBeNull();
  });

  it('成功后把「所有设备（含当前这台）都要重新登录」这句说出来', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    vi.spyOn(API, 'setPassword').mockResolvedValue(undefined as never);
    renderDlg('set_password');
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.change(screen.getByLabelText('新密码'), { target: { value: 'newpw123456' } });
    fireEvent.click(screen.getByRole('button', { name: '确认修改' }));
    /* 这不是客套话：P1 之后改密码**当场作废已签发的每一张票**，而 /auth/set-password
       不发新票 ⇒ 用户在**自己正用的这台设备上**也会被踢回登录页。文案不把这两句说出来，
       用户就是莫名其妙掉线。两条断言分别钉住「范围含当前这台」与「要重新登录」——
       把旧文案（不会被强制退出 / 90 天）放回兜底串，两条都会红。 */
    await waitFor(() => expect(screen.getByText(/包括当前这台/)).toBeInTheDocument());
    expect(screen.getByText(/重新登录/)).toBeInTheDocument();
  });

  it('purpose=set_password 时不渲染同意勾选框，也不要求勾选就能发验证码', async () => {
    /* 裁定：set_password 的前置就是这个号已经绑在这个账号上（未绑号已经改成引导去绑），
       收集手机号的同意在绑定那一刻已经给过 —— 再问一次是为已经持有的数据要同意。 */
    const spy = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderDlg('set_password');
    expect(screen.queryByRole('checkbox')).toBeNull();
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });

  it('绑定模式不受影响：同意项还在，未勾时发不了码（Task 16 那条口径的回归）', () => {
    renderDlg('bind');
    expect(screen.getByRole('checkbox', { name: /隐私/ })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeDisabled();
  });
});
