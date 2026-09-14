import { screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { API } from '../../../../api';
import { renderLoginModal } from './renderLoginModal';

/* 登录态做成可变 fixture —— 手法与 ReportsPage.test.tsx:26-37 同源。
   `useAuth` 没有 Provider 时会抛（AuthContext.tsx:211），所以这里整个换掉。
   注意 `vi.mock` 只 mock 了 `useAuth`：本文件的渲染树里没人用 `AuthProvider`。 */
let authFixture: {
  user: null;
  isAuthenticated: boolean;
  isLoading: boolean;
  token: null;
  phoneLoginEnabled: boolean;
  login: ReturnType<typeof vi.fn>;
  loginByPhone: ReturnType<typeof vi.fn>;
  refreshUser: ReturnType<typeof vi.fn>;
  logout: ReturnType<typeof vi.fn>;
};

function resetAuth() {
  authFixture = {
    user: null, isAuthenticated: false, isLoading: false, token: null, phoneLoginEnabled: true,
    login: vi.fn().mockResolvedValue(undefined),
    loginByPhone: vi.fn().mockResolvedValue(undefined),
    refreshUser: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
  };
}
resetAuth();

vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

/* 区号选择器用 `<TextField select label="国家/地区">` 写，它**自己把 labelId 接上了**，
   所以 `getByRole('combobox', { name })` 直接解析得出可访问名。
   不要抄 AiSetupPage.test.tsx:143-148 那个 `comboboxForLabel` 助手 —— 它是为
   `FormControl + InputLabel + Select`（没接 labelId）写的，抄过来会把判据从可访问性
   挪到 `.MuiFormControl-root` 这个实现细节上。 */
const countryCombobox = () => screen.getByRole('combobox', { name: '国家/地区' });

const toPhoneMode = () => fireEvent.click(screen.getByText('验证码登录'));

/* 「填号 + 点获取验证码」只写这一处：Task 15 会给发码按钮加上「必须先勾同意项」
   这个前置条件，那时**只改这个助手一行**，所有用到它的用例一起跟上。
   （散在五条用例里各写一遍，Task 15 就要改五处，漏一处红一条。） */
const requestCode = (phone = '13800138000') => {
  fireEvent.change(screen.getByLabelText('手机号'), { target: { value: phone } });
  // Task 15：发码按钮多了「必须先勾同意项」这个前置条件。改在助手里的这一行，
  // 六条走 requestCode 的用例一起跟上。
  fireEvent.click(screen.getByRole('checkbox', { name: /隐私/ }));
  fireEvent.click(screen.getByRole('button', { name: '获取验证码' }));
};

const fillCodeFlow = async (phone = '13800138000', code = '123456') => {
  requestCode(phone);
  await waitFor(() => expect(API.sendPhoneCode).toHaveBeenCalled());
  fireEvent.change(screen.getByLabelText('验证码'), { target: { value: code } });
  fireEvent.click(screen.getByRole('button', { name: '登录' }));
};


describe('LoginModal 手机验证码模式', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetAuth();
    /* SettingsProvider 挂载即 i18n.loadTranslations → API.getTranslations → 全局 fetch。
       喂一份空字典：i18n.t(key, 默认值) 于是恒返默认值，下面的中文字面量才能命中
       （i18n.ts:52 `this.translations[key] || defaultText || key`）。
       手法同 GalaxySidebar.test.tsx:41。
       实证过这不是**必需**（ReportsPage.test.tsx 不 stub 也绿，因为 i18n.ts:28-30 自己吞异常），
       但 stub 掉更确定 —— 而且本 worktree 一个 .mo 都没有，字典本来就取不到。 */
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('默认是密码模式，能切到验证码模式', () => {
    renderLoginModal();
    expect(screen.getByLabelText('用户名')).toBeInTheDocument();
    toPhoneMode();
    expect(screen.getByLabelText('手机号')).toBeInTheDocument();
    expect(screen.queryByLabelText('密码')).toBeNull();
    expect(screen.queryByLabelText('用户名')).toBeNull();
  });

  it('验证码模式的必填校验说的是手机号，不再被「请填写全部字段」短路', () => {
    /* 旧守卫是 LoginModal.tsx:27 的 `if (!username || !password)` —— 验证码模式下
       两个都空，提交当场短路。这条用例就是钉那一处（review #27）。 */
    renderLoginModal();
    toPhoneMode();
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    expect(screen.getByText('请填写手机号')).toBeInTheDocument();
    expect(screen.queryByText('请填写全部字段')).toBeNull();
  });

  it('发码按钮在倒计时期间禁用并显示剩余秒数', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    requestCode();
    await waitFor(() => expect(screen.getByRole('button', { name: /60 秒/ })).toBeDisabled());
  });

  it('成功文案是「已提交发送」不是「已发送到您的手机」', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    requestCode();
    // 我们没有回执，不知道有没有到 —— 说「已发送到您的手机」是在替运营商担保。
    await waitFor(() => expect(screen.getByText(/已提交发送/)).toBeInTheDocument());
    expect(screen.queryByText(/已发送到您的手机/)).toBeNull();
  });

  it('限流时显示后端给的具体原因，不显示通用「操作失败」', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockRejectedValue(
      Object.assign(new Error('x'), { code: 'sms_cooldown', retryAfterSec: 42, status: 429 }));
    renderLoginModal();
    toPhoneMode();
    requestCode();
    await waitFor(() => expect(screen.getByText(/还需等待 42 秒/)).toBeInTheDocument());
    expect(screen.queryByText(/操作失败/)).toBeNull();
  });

  it('未绑号的 404 给出可走的路，不是干巴巴的失败', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    authFixture.loginByPhone.mockRejectedValue(
      Object.assign(new Error('x'), { code: 'phone_not_bound', status: 404 }));
    renderLoginModal();
    toPhoneMode();
    await fillCodeFlow();
    await waitFor(() => expect(screen.getByText(/还没有绑定账号/)).toBeInTheDocument());
    expect(screen.getByText(/绑定手机号/)).toBeInTheDocument();   // 指得出下一步去哪
  });

  it('区号选择器默认 +86，改成 +81 后取的是 +81 拼出来的号', async () => {
    const send = vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    expect(countryCombobox()).toHaveTextContent('+86');
    const user = userEvent.setup();
    await user.click(countryCombobox());
    await user.click(await screen.findByRole('option', { name: /\+81/ }));
    requestCode('9012345678');
    // 断言落在「发出去的号」上，不落在「下拉里显示什么」上 —— 后者选中了也可能没接进去。
    await waitFor(() => expect(send).toHaveBeenCalledWith('+819012345678', 'login'));
  });

  it('这台服务器没有手机功能：登录框里「验证码登录」与「忘记密码？」都不画', () => {
    /* 「忘记密码？」也在内 —— 它走的就是验证码登录那条路（下一条用例钉着），
       不是另一条独立的重置流程。画出来点下去只会撞上 404。
       注册那一项与手机无关，必须还在：否则这条断言证明的是「整个链接区没渲染」。 */
    authFixture.phoneLoginEnabled = false;
    renderLoginModal();
    expect(screen.queryByText('验证码登录')).toBeNull();
    expect(screen.queryByText('忘记密码？')).toBeNull();
    expect(screen.getByText('还没有账号？注册')).toBeInTheDocument();
  });

  it('「忘记密码？」切到验证码登录，不跳独立重置流程', () => {
    renderLoginModal();
    fireEvent.click(screen.getByText('忘记密码？'));
    expect(screen.getByLabelText('手机号')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeInTheDocument();
  });

  it('切回密码模式再切回来，手机号/验证码/倒计时全部复位', async () => {
    vi.spyOn(API, 'sendPhoneCode').mockResolvedValue({ challenge_id: 'c1', cooldown_sec: 60 });
    renderLoginModal();
    toPhoneMode();
    requestCode();
    fireEvent.change(screen.getByLabelText('验证码'), { target: { value: '123456' } });
    await waitFor(() => expect(screen.getByRole('button', { name: /60 秒/ })).toBeDisabled());
    fireEvent.click(screen.getByText('密码登录'));
    toPhoneMode();
    // 上一位用户的手机号不许留在框里，倒计时也不许还在跑。
    expect(screen.getByLabelText('手机号')).toHaveValue('');
    expect(screen.getByLabelText('验证码')).toHaveValue('');
    /* 倒计时复位的判据落在**按钮文案**上，不落在 disabled 上：
       Task 15 给发码按钮加了第二个前置条件（必须先勾同意项），
       disabled 从此是「倒计时 OR 未同意」的合成量，拿它判倒计时会把两件事混在一起。 */
    expect(screen.queryByRole('button', { name: /秒后可重发/ })).toBeNull();
    // 同意项也一并复位了 —— 上一位用户的同意不替下一位作数，所以此刻按钮**应当**禁用。
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeDisabled();
    fireEvent.click(screen.getByRole('checkbox', { name: /隐私/ }));
    expect(screen.getByRole('button', { name: '获取验证码' })).not.toBeDisabled();
  });
});
