import { screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PRIVACY_PATH } from '../../../../legal/privacy';
import { renderLoginModal } from './renderLoginModal';

/* 装配与 LoginModal.phone.test.tsx 同源（renderLoginModal 只装 Settings + Router，
   AuthContext 必须各测试文件自己 vi.mock —— vi.mock 只有写在测试文件里才被提升）。 */
let authFixture: Record<string, unknown>;
function resetAuth() {
  authFixture = {
    user: null, isAuthenticated: false, isLoading: false, token: null, phoneLoginEnabled: true,
    login: vi.fn(), loginByPhone: vi.fn(), refreshUser: vi.fn(), logout: vi.fn(),
  };
}
resetAuth();
vi.mock('../../../../context/AuthContext', () => ({ useAuth: () => authFixture }));

const toPhoneMode = () => fireEvent.click(screen.getByText('验证码登录'));

/* 按 `/隐私/` 取而不是 `/隐私政策/`：仓里与设计稿一律写「隐私**策略**」
   （`PRIVACY_TITLE = '智星盒隐私策略'`、smart-board.pen 的 `《隐私策略》`）。
   判据钉死其中一种写法，日后一次纯文案统一就会让它凭空变红，而红的原因与功能无关。

   ⚠️ 不给 Checkbox 配 `inputProps={{'aria-label': …}}`：实测那样会把可访问名从
   「我已同意…《隐私策略》」**截短**成「《隐私策略》」—— 一个同意勾选框丢掉的恰好是同意那半句。
   FormControlLabel 的 <label> 本来就包住 input，隐式关联已经成立，不加也取得到。 */
const consentBox = () => screen.getByRole('checkbox', { name: /隐私/ }) as HTMLInputElement;

describe('手机号收集的告知与单独同意', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    resetAuth();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ translations: {} }) }));
  });

  it('验证码模式下同意项默认不勾选', () => {
    renderLoginModal();
    toPhoneMode();
    expect(consentBox().checked).toBe(false);
  });

  it('未勾选时「获取验证码」不可点 —— 不许先发了码再问', () => {
    renderLoginModal();
    toPhoneMode();
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    expect(screen.getByRole('button', { name: '获取验证码' })).toBeDisabled();
  });

  it('勾上之后才可点', () => {
    renderLoginModal();
    toPhoneMode();
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(consentBox());
    expect(screen.getByRole('button', { name: '获取验证码' })).not.toBeDisabled();
  });

  it('同意项是单独的 —— 不与服务条款合并成一个勾选', () => {
    renderLoginModal();
    toPhoneMode();
    const label = consentBox().closest('label')!.textContent!;
    // 「我已阅读并同意《服务条款》和《隐私策略》」这种打包写法不合格。
    expect(label).not.toMatch(/服务条款|用户协议/);
    /* 正判必须配一条：纯反判对「文案整项没了」免疫 —— 实测把 label 换成空的，
       上面那句照样 PASS。有什么和没有什么各守一半。 */
    expect(label).toMatch(/我同意/);
    expect(label).toMatch(/隐私/);
  });

  it('明写收集什么、干什么用、由谁收 —— 只给一个链接不算告知', () => {
    renderLoginModal();
    toPhoneMode();
    const text = screen.getByTestId('phone-consent').textContent!;
    expect(text).toMatch(/手机号/);
    /* 只断「身份验证」不断「登录」：同一个 Dialog 里到处都是「登录」，
       说明句被删而别处文案漏进这个 testid 时，按 /登录/ 判会是绿的。 */
    expect(text).toMatch(/身份验证/);
    // PIPL 十七条要告知的是个人信息处理者的**名称**，不是产品名。
    expect(text).toMatch(/北京万智星科技有限公司/);
  });

  it('密码登录模式下不出现这个同意项 —— 那里不收集手机号', () => {
    renderLoginModal();
    expect(screen.queryByTestId('phone-consent')).toBeNull();
  });

  it('切走再切回来，同意状态复位成未勾 —— 上一位用户的同意不替下一位作数', () => {
    renderLoginModal();
    toPhoneMode();
    fireEvent.click(consentBox());
    expect(consentBox().checked).toBe(true);
    fireEvent.click(screen.getByText('密码登录'));
    toPhoneMode();
    expect(consentBox().checked).toBe(false);
  });

  it('点「取消」关掉弹窗，手机号与同意状态都不留给下一位', () => {
    /* Dialog 关着时 LoginModal 仍然挂载，state 不会自己没。
       本用例里父层不翻 `open` prop，所以点完取消复位与否当场可见。
       切模式那条路上面已经有用例守着了，但「点取消 / 点遮罩」才是更常走的那条 —— 
       这一条之前 Task 14/15 两份计划都没覆盖。 */
    renderLoginModal();
    toPhoneMode();
    fireEvent.change(screen.getByLabelText('手机号'), { target: { value: '13800138000' } });
    fireEvent.click(consentBox());
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.getByLabelText('用户名')).toBeInTheDocument();   // 复位回密码模式
    toPhoneMode();
    expect(screen.getByLabelText('手机号')).toHaveValue('');
    expect(consentBox().checked).toBe(false);
  });

  it('链接指向的就是路由表里那条路径', () => {
    renderLoginModal();
    toPhoneMode();
    const link = screen.getByRole('link', { name: /隐私/ });
    /* 必须用 getAttribute 不能用 `.href` 属性 —— jsdom 会把后者解析成
       `http://localhost:3000/galaxy/privacy`，toBe 当场红。
       断言落在 href 与常量的相等上；「这条路径真的渲染政策页」由 PrivacyPage.test.tsx 证：
       到达性只证得到自己这一层，堵点按定义在更外面。 */
    expect(link.getAttribute('href')).toBe(PRIVACY_PATH);
    // 外链新开一页：同一页跳走会把填了一半的手机号/验证码连同弹窗一起冲掉。
    expect(link.getAttribute('target')).toBe('_blank');
  });
});
