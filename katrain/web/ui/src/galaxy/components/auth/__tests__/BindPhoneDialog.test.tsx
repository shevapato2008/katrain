import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { SettingsProvider } from '../../../../context/SettingsContext';
import { API } from '../../../../api';
import BindPhoneDialog from '../BindPhoneDialog';

let authFixture: { user: { id: number; username: string; phone_bound: boolean } | null;
                   refreshUser: ReturnType<typeof vi.fn> };
function resetAuth(bound = false) {
  authFixture = {
    user: { id: 1, username: 'u', phone_bound: bound },
    refreshUser: vi.fn().mockResolvedValue(undefined),
  };
}
resetAuth();
vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

const renderDialog = (onClose = vi.fn()) => {
  const r = render(
    <MemoryRouter><SettingsProvider>
      <BindPhoneDialog open onClose={onClose} />
    </SettingsProvider></MemoryRouter>,
  );
  return { ...r, onClose };
};

/* 按 `/隐私/` 取，不是 `/隐私政策/`：Task 15 把 PhoneConsent 的链接文案定成《隐私**策略**》
   （与 `PRIVACY_TITLE = '智星盒隐私策略'` 和设计稿一致）。写死其中一种，
   日后一次纯文案统一就会让判据凭空变红。 */
const consentBox = () => screen.getByRole('checkbox', { name: /隐私/ }) as HTMLInputElement;

describe('BindPhoneDialog', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetAuth();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('同意项默认不勾，未勾时不能发码 —— 与登录框同一条口径', () => {
    renderDialog();
    expect(consentBox().checked).toBe(false);
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeDisabled();
  });

  it('发码用的 purpose 是 bind，不是 login', async () => {
    // purpose 走错，后端 verify_and_consume 会以 challenge_purpose_mismatch 拒掉，
    // 而用户看到的是一句莫名其妙的失败。
    const send = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderDialog();
    fireEvent.click(consentBox());
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(send).toHaveBeenCalledWith('+8613800138000', 'bind'));
  });

  it('绑定成功后刷新用户资料并关闭 —— 额度文案要当场翻面', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    const bind = vi.spyOn(API, 'bindPhone').mockResolvedValue({ phone_masked: '+86 138****8000' });
    const { onClose } = renderDialog();
    fireEvent.click(consentBox());
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: '绑定' }));
    await waitFor(() => expect(bind).toHaveBeenCalledWith('c1', '123456'));
    // 不刷新的话，user.phone_bound 还是 false，复盘页文案和侧栏入口都不会变。
    await waitFor(() => expect(authFixture.refreshUser).toHaveBeenCalled());
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('号被别人占了时说清楚是哪一种失败，并指出可走的路', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    vi.spyOn(API, 'bindPhone').mockRejectedValue(
      Object.assign(new Error('x'), { code: 'phone_taken', status: 409 }));
    renderDialog();
    fireEvent.click(consentBox());
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
    await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    fireEvent.click(screen.getByRole('button', { name: '绑定' }));
    /* 断言按 `auth:err_phone_taken` 在 Task 14 就定下的那份默认值走
       （'这个号已经有账号了，可以直接用验证码登录那个账号'）——
       一个键只该有一份文案，不给绑定场景再写第二份。 */
    await waitFor(() => expect(screen.getByText(/已经有账号/)).toBeInTheDocument());
    expect(screen.getByText(/验证码登录/)).toBeInTheDocument();   // 指出那个号可以直接登录
    expect(authFixture.refreshUser).not.toHaveBeenCalled();
  });
});
