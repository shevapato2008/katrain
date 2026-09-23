import { useNavigate } from 'react-router-dom';

import { useAuth } from '../../../context/AuthContext';
import { useTranslation } from '../../../hooks/useTranslation';
import { useAiLadderStatus } from '../../../features/aiLadder/useAiLadderStatus';
import { LAUNCHER_LOGIN_URL, LAUNCHER_REGISTER_URL, isStrictBoxKiosk, leaveToLauncher } from '../../shell/boxUrls';
import KioskAiLadderRows from './KioskAiLadderRows';

/**
 * 设置屏「账号与平台」那一组的前两行。
 *
 * 2026-08-23 从 MUI 卡片重排成外壳的 `.kiosk-row` —— 上一版是一张 `background.paper` 的卡
 * 加一条满宽的红色退出按钮,夹在两组 `.kiosk-row` 中间**像是从别的应用里剪进来的**。
 * 现在它就是两行:一行账号,一行 AI 段位。
 *
 * 段位那一行和它的详情在 `KioskAiLadderRows`:2026-09 起详情**就地展开**成几行外壳行,
 * 不再是一个装着 galaxy 那张 MUI 卡的对话框。
 */
export default function AccountSection() {
  const { user, logout, token, isGuest } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { status, retry } = useAiLadderStatus(token ?? undefined, Boolean(user) && !isGuest);

  /**
   * 出厂盒子上**围棋退不了登录**，所以这里不假装自己能。三条实测事实：
   *
   * 1. `POST /api/v1/auth/logout` 在 strict 档下函数体第一句就 403
   *    (`katrain/web/api/v1/endpoints/auth.py:382-386`，文案“Use Box SSO bridge clear”)，
   *    而前端把它 catch 掉只 `console.warn`。
   * 2. 就算那一行 403 不在，它要清的 key 也是 `sb_token`，而盒端的 cookie 叫
   *    `sb_go_token` —— **整个 katrain 包里没有任何一行 Python 写过 `sb_go_token`**，
   *    种它和清它的都是 launcher(`setup-wizard`)。
   * 3. 于是旧写法的真实效果是：只清 React state → 弹到登录页 → 刷新一下
   *    又被同一张 cookie 认回来。一颗“退出吗退不掉”的键，还顺手把人送进
   *    `KioskLayout` 外面那一屏(无顶栏/无 Dock/无主页键)。
   *
   * 另外三家(象棋/五子棋/国象)根本没有模块内退出登录 —— 身份归 launcher。
   * 所以盒端走“去主页切账号”。**不能带 `?logout=1`**，理由见 `shell/boxUrls.ts`。
   */
  const handleLogout = async () => {
    if (isStrictBoxKiosk) {
      leaveToLauncher();
      return;
    }
    await logout();
    navigate('/kiosk/login', { replace: true });
  };

  return (
    <>
      <div className="kiosk-row">
        <span className="kiosk-row__t">
          <b>{isGuest ? t('Guest', '访客') : (user?.username ?? t('Guest', '访客'))}</b>
          <em>
            {isGuest
              ? t('Not signed in', '未登录')
              : user
              ? `${t('Signed in', '已登录')} · ${isStrictBoxKiosk
                  ? t('settings:box_account_owned_by_home', '智星盒账户，全盒共用')
                  : t('StellaBox account', '智星盒账户')}`
              : t('settings:guest_sub', '这台盒子上的本地档案')}
          </em>
        </span>
        <span className="kiosk-row__end">
          {isGuest ? (
            <button
              type="button"
              className="kiosk-btn kiosk-btn--secondary"
              data-testid="account-register-login"
              onClick={() => leaveToLauncher(LAUNCHER_REGISTER_URL)}
            >
              {t('Register / Sign in', '注册 / 登录')}
            </button>
          ) : user ? (
            <button
              type="button"
              className={isStrictBoxKiosk ? 'kiosk-btn kiosk-btn--pill' : 'kiosk-btn kiosk-btn--pill rvdanger'}
              data-testid="settings-logout"
              onClick={() => void handleLogout()}
            >
              {isStrictBoxKiosk
                ? t('settings:switch_account_at_home', '在主页切账号')
                : t('Sign out', '退出登录')}
            </button>
          ) : (
            <button
              type="button"
              className="kiosk-btn kiosk-btn--secondary"
              onClick={() => (isStrictBoxKiosk ? leaveToLauncher(LAUNCHER_LOGIN_URL) : navigate('/kiosk/login'))}
            >
              {t('settings:sign_in', '登录')}
            </button>
          )}
        </span>
      </div>

      {/* 游客 / 未登录不请求段位(`useAiLadderStatus` 第二个参数),这里也不画。 */}
      {user && !isGuest && <KioskAiLadderRows status={status} onRetry={retry} />}
    </>
  );
}
