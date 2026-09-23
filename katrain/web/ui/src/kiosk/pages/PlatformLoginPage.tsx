import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API } from '../../api';
import { platformErrorMessage } from '../utils/platformErrorMessage';
import { interpolate } from '../utils/interpolate';
import { useKeyboardInset } from '../hooks/useKeyboardInset';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskOptSeg } from '../shell/KioskOptSeg';
import { PLATFORM_META } from '../constants/platforms';
import { PlatformLoginAside } from '../components/platform/PlatformLoginAside';

/**
 * 登录独立成页(屏 07b/08,`sample-go/shots/07b-platform-login-pw.png` /
 * `08-platform-login-ogs.png`,L2 布局 B)。取代 `PlatformConnectPage` 里原来那段
 * 页内登录表单 —— 判例仍是屏 04「点此输入」药丸那条(真页面上必须真能输入,
 * 不做「点了弹一层」),只是从「页内一段」换成了「独立一页」。
 *
 * ## 标签集合从一张表推导(R-19)
 *
 * 这一轮只出**验证码 / 密码**两个标签,默认**密码**;扫码留给 Task 6(后端正在并行写)。
 * 画一个点了没反应的标签 = 状态不诚实,所以这一轮干脆不画。`LOGIN_MODE_TABS` 是那张表 ——
 * Task 6 只需往表里加一项、把默认值换成扫码,不改这里的渲染逻辑。
 * `PLATFORM_LOGIN_MODES` 是「这一家支持哪几种」:野狐到不了这一屏(`comingSoon`,
 * `PlatformConnectPage`/`PlayPage` 已经把它挡在外面),所以这张表只列 golaxy/ogs。
 * OGS 只有一种 ⇒ 标签栏整条不渲染(一个选项的分段控件是假的选择,同一条判例)。
 *
 * ## 星阵不论哪个标签,账号字段都是手机号
 *
 * 设计源 07b(密码标签)markup 里字段仍标「手机号」,不是「用户名」——星阵的账号体系
 * 本身就是手机号,密码只是换了一种凭证,不是换了一种账号。
 *
 * ## API 契约(`src/api.ts:641-647`,不改)
 *
 * `platformLogin(platform, { username, password?, sms_code? }, token)`——验证码模式发
 * `sms_code`,密码模式发 `password`,两种模式的 `username` 都是这个页面「账号」那一格的值
 * (星阵是手机号,OGS 是用户名)。
 */

type LoginMode = 'sms' | 'password';

interface LoginModeTab { mode: LoginMode; labelKey: string; labelZh: string; }

/** 这一轮的标签集合。顺序即渲染顺序;默认取 `password`(见组件里 `useState` 初值)。 */
const LOGIN_MODE_TABS: LoginModeTab[] = [
  { mode: 'sms', labelKey: 'platform:login_tab_sms', labelZh: '验证码' },
  { mode: 'password', labelKey: 'platform:login_tab_password', labelZh: '密码' },
];

/** 这一家支持哪几种登录方式。只列今天真能登录的两家(见头注)。 */
const PLATFORM_LOGIN_MODES: Record<string, readonly LoginMode[]> = {
  golaxy: ['sms', 'password'],
  ogs: ['password'],
};

/** 星阵能给的对手是那 39 档 bot,不是人 ⇒ 登录成功进人机开局;其余家进大厅。
 * 这条判据和 `PlayPage`/`PlatformConnectPage` 里「`supports_engine_play` 决定去向」
 * 是同一件事的静态版本 —— 登录刚成功那一刻还没有新的 `/platforms` 数据可读,
 * 而「星阵进人机开局、其余进大厅」今天是协议层面的恒定事实(PROTOCOL.md),不是要猜的。 */
const engineCapable = (platform: string) => platform === 'golaxy';

const PlatformLoginPage = () => {
  const { t } = useTranslation();
  const { platform = '' } = useParams<{ platform: string }>();
  const { token, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const modes = PLATFORM_LOGIN_MODES[platform] ?? ['password'];
  const tabs = LOGIN_MODE_TABS.filter((tab) => modes.includes(tab.mode));
  const [mode, setMode] = useState<LoginMode>(modes.includes('password') ? 'password' : modes[0]);

  const [account, setAccount] = useState('');
  const [secret, setSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [smsBusy, setSmsBusy] = useState(false);
  const [smsLeft, setSmsLeft] = useState(0);

  // 软键盘避让(承重,见 `useKeyboardInset` 头注)。这一屏没有 `PlatformConnectPage` 那个
  // 整栏滚的 `.kiosk-side__scroll` —— `.xplogin` 是 `overflow:hidden` + 垂直居中,
  // 垫 padding 换不来任何可滚的余量,照搬会得到一个「跑了、没效果」的 hook。
  // 真正能滚的容器是 `.xplogin__main`(`go-screens.css` 已经把它改成 `overflow-y:auto`)。
  useKeyboardInset('[data-testid="platform-login-page"] .xplogin__main');

  const meta = PLATFORM_META[platform];
  const name = meta ? t(meta.label, meta.labelCn) : platform;
  const isSms = mode === 'sms';

  const sub = isSms
    ? t('platform:login_sub_sms', '未连接 · 用手机验证码登录')
    : interpolate(t('platform:login_sub_password', '未连接 · 用{name}的账号密码登录'), { name });

  const switchMode = (next: LoginMode) => {
    setMode(next);
    setSecret('');
    setError('');
  };

  const sendSms = async () => {
    if (!isAuthenticated) return;
    if (!account.trim()) { setError(t('platform:need_phone', '请先输入手机号')); return; }
    setSmsBusy(true);
    setError('');
    try {
      await API.platformSmsRequest(platform, account, token);
      setSmsLeft(60);
    } catch (e) {
      setError(platformErrorMessage(e, t('platform:sms_failed', '验证码没发出去')));
    } finally {
      setSmsBusy(false);
    }
  };

  const submit = async () => {
    if (!isAuthenticated) return;
    setBusy(true);
    setError('');
    try {
      await API.platformLogin(
        platform,
        isSms ? { username: account, sms_code: secret } : { username: account, password: secret },
        token,
      );
      navigate(engineCapable(platform)
        ? `/kiosk/play/cross-platform/engine/${platform}`
        : `/kiosk/play/cross-platform/lobby?platform=${platform}`);
    } catch (e) {
      setError(platformErrorMessage(e, t('platform:login_failed', '登录失败')));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="kiosk-layout-b" data-testid="platform-login-page">
      <KioskPagebar
        backLabel={t('Back to play', '返回对弈')}
        onBack={() => navigate('/kiosk/play/cross-platform')}
        title={name}
        sub={sub}
      />
      <section className="setgrp inputgrp xplogin">
        <PlatformLoginAside platform={platform} />
        <div className="xplogin__main">
          <div className="xpcol">
            <KioskSecLabel zh={interpolate(t('platform:login_title', '登录{name}'), { name })} en="Sign in" />

            {tabs.length > 1 && (
              <span className="xptabs">
                <KioskOptSeg
                  options={tabs.map((tab) => ({ value: tab.mode, label: t(tab.labelKey, tab.labelZh) }))}
                  value={mode}
                  onChange={(next) => switchMode(next)}
                  ariaLabel={t('platform:login_tabs', '登录方式')}
                  testId="login-mode-tabs"
                />
              </span>
            )}

            <div className="igrow">
              <span className="iglab">
                {platform === 'golaxy' ? t('platform:login_field_phone', '手机号') : t('Username', '用户名')}
              </span>
              <input
                className="xpfield"
                data-testid="login-field-user"
                type={platform === 'golaxy' ? 'tel' : 'text'}
                aria-label={platform === 'golaxy' ? t('platform:login_field_phone', '手机号') : t('Username', '用户名')}
                placeholder={t('local:tap_to_type', '点此输入')}
                value={account}
                onChange={(e) => setAccount(e.target.value)}
              />
            </div>

            <div className="igrow">
              <span className="iglab">
                {isSms ? t('platform:login_field_code', '验证码') : t('Password', '密码')}
              </span>
              {isSms ? (
                <>
                  <input
                    className="xpfield"
                    data-testid="login-field-password"
                    type="text"
                    aria-label={t('platform:login_field_code', '验证码')}
                    placeholder={t('local:tap_to_type', '点此输入')}
                    value={secret}
                    onChange={(e) => setSecret(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') void submit(); }}
                  />
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--pill"
                    data-testid="login-sms-request"
                    disabled={smsBusy || smsLeft > 0}
                    onClick={() => { void sendSms(); }}
                  >
                    {smsLeft > 0
                      ? interpolate(t('platform:sms_again', '{n} 秒后可重发'), { n: smsLeft })
                      : t('platform:sms_get', '获取验证码')}
                  </button>
                </>
              ) : (
                <input
                  className="xpfield"
                  data-testid="login-field-password"
                  type="password"
                  aria-label={t('Password', '密码')}
                  placeholder={t('local:tap_to_type', '点此输入')}
                  value={secret}
                  onChange={(e) => setSecret(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') void submit(); }}
                />
              )}
            </div>

            {/* 登录出错要有落点 —— 没有落点的错误等于没报错。平台给的话原样显示,不换成自己编的。 */}
            {error && <p className="loginerr" data-testid="login-error">{error}</p>}

            <div className="igrow">
              <span className="iglab" />
              <button
                type="button"
                className="kiosk-btn kiosk-btn--primary xpgo"
                data-testid="login-submit"
                disabled={busy}
                onClick={() => { void submit(); }}
              >
                {busy
                  ? t('platform:logging_in', '正在登录…')
                  : interpolate(t('platform:login_title', '登录{name}'), { name })}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default PlatformLoginPage;
