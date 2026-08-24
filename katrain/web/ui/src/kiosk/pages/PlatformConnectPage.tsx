import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API, type PlatformInfo } from '../../api';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { PLATFORM_META, defaultPlatforms, mergePlatformStatus } from '../constants/platforms';
import { interpolate } from '../utils/interpolate';

/**
 * 屏 07 跨平台 · 连接(`sample-go/shots/07-platform.png`,L2 布局 B)。
 *
 * 首页「跨平台对弈」那三张卡未连接时全都落到这儿。三件事必须画对,少一件这一屏就白画了:
 *
 * ① **每家支持什么不一样**,四个能力标由 `/platforms` 下发,不是界面写死的四个格子。
 *    亮着的才是那一家真支持的。
 * ② **登录字段跟着平台换** —— OGS 是用户名 + 密码,星阵是手机号 + 验证码。
 *    给一套通用表单是错的,那会让星阵那家永远登不上去。
 * ③ **已连接的那家进的是大厅还是人机开局**,取决于 `supports_engine_play` ——
 *    星阵能给的对手是那 39 档 bot 不是人(`get_online_users` 直接 `return []`),
 *    所以它进人机开局;OGS 进大厅。
 *
 * ## 三处按 2026-08-24 的裁定落的
 *
 * **登录是页内一段,不是弹层。** 判例在仓里:屏 04 那两颗「点此输入」药丸
 * (`go-screens.css` 的 `.nameinput` 那一段)——「静态稿只能画到药丸这一步,真页面上它必须
 * 真能输入……**不做「点药丸弹一个输入框」**,那是稿子上没有的一层流程」。这里是同一个构件。
 * 改成弹层还会把一整段从四图里拿掉。
 *   · 默认目标 = 显示顺序里第一个「**可登录且未连接**」的平台(可登录 = `PLATFORM_META` 里
 *     有 `login` 且不是 `comingSoon`)。稿子那一帧 OGS 已连、野狐 comingSoon ⇒ 落到星阵,
 *     标题正是「登录 · 星阵围棋」。**推导出来的,不是写死的。**
 *   · 点某一行的「登录」= 把那一家设为这一段的目标(换标题、换字段、清空表单),不弹任何东西。
 *   · **三家全连上 ⇒ 整段不渲染。** 每一行都写着「已连接」,那就是答案;再加一句
 *     「都连上了」正是 Fan 8-22 要砍的小字。
 *   · 两家未连接**仍然只有一段**,目标跟着点谁走 —— 叠两段只会把第二段埋得更深。
 *
 * **登出留在行尾,而且要有字。** 稿子那一行只有「已连接」+「进入大厅」,这一处是
 * **实现反过来纠正稿子**:登出是业务动作,规范 §11 明写「悔棋、认输、求和、提示这些
 * 业务动作一律不许上页控条」;收进登录段也不行 —— 三家全连上时那段不渲染,而那正是
 * 最需要登出的时候。行尾也不挤:这一屏是布局 B 通栏 992,能力标右缘到行尾之间空着 545px。
 * 误触的代价在星阵那家是重走一遍短信,所以走一次确认弹层(和屏 08 的「挑战」同一条规矩)。
 *
 * **野狐那一行行尾是一枚警示标,没有按钮。** 稿子那枚 `.wip`「对弈未接后端」是
 * **给读稿人看的进度标注**,不上屏(屏 15 / 19 已按这条处理过);但它编码的**产品事实
 * 今天仍然成立**,得换成这一屏自己的词汇留在屏上。不写「即将上线」——挡路的是 protobuf
 * WebSocket 客户端要重建(`platforms/fox/adapter.py` 里 `submit_move` / `submit_pass` /
 * `resign` 三个 NotImplementedError),**没人给过日期,那是预测不是状态**;这条 track 在
 * 屏 01 判过同型:「接口没通的平台不许摆成锁着的样子」——再推一步就是也不许摆成马上要来的样子。
 * 也不写「不能对弈」(读起来像野狐这个平台不能下棋,假的)。
 *
 * ⚠️ **`supports_*` 和行尾说的是两件事,不许互相覆盖。** 核过三家:OGS `supports_rooms=False`;
 * 星阵和野狐都 `True` 而 `get_rooms()` 都返回 `[]`。`supports_*` 说的是「**那个平台**有没有
 * 这件事」,行尾说的是「**这台盒子现在**能不能干这件事」。能力标照下发原样渲染,前端不修正。
 *
 * ⚠️ 登记(不在本轮):屏 01 那张野狐卡今天还写着「即将上线」。该把这句话做成
 * `constants/platforms.ts` 里的一个常量、两屏共读;闸查「两屏引用同一个标识符」,
 * 不查两处字面量长得一样。
 */

/** 这一家现在能不能走登录这条路。`comingSoon` 的家有 `login` 配置,但登进去也没法下。 */
const canLogIn = (platform: string): boolean => {
  const meta = PLATFORM_META[platform];
  return !!meta?.login && !meta.comingSoon;
};

const PlatformConnectPage = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();

  const [platforms, setPlatforms] = useState<PlatformInfo[]>(defaultPlatforms);
  const [loaded, setLoaded] = useState(false);
  /** 用户点过某一行的「登录」之后,这一段的目标就跟着他走;`null` = 还没点过,按默认推。 */
  const [picked, setPicked] = useState<string | null>(null);
  const [form, setForm] = useState({ user: '', pass: '' });
  const [loginBusy, setLoginBusy] = useState(false);
  const [loginError, setLoginError] = useState('');
  const [smsBusy, setSmsBusy] = useState(false);
  const [smsLeft, setSmsLeft] = useState(0);
  const [logoutTarget, setLogoutTarget] = useState<string | null>(null);
  const loginSectionRef = useRef<HTMLElement | null>(null);

  const refresh = useCallback(async () => {
    if (!token) { setLoaded(true); return; }
    try {
      const data = await API.platformStatus(token);
      setPlatforms(mergePlatformStatus(data.platforms));
    } catch {
      // 问不到就摆一份全 false 的:能力标全暗、行尾只给登录。**不伪造乐观默认。**
      setPlatforms(defaultPlatforms());
    } finally {
      setLoaded(true);
    }
  }, [token]);

  useEffect(() => { void refresh(); }, [refresh]);

  // 验证码倒计时:每一跳重新挂一个 1s 的 timeout,到 0 为止。
  useEffect(() => {
    if (smsLeft <= 0) return undefined;
    const id = setTimeout(() => setSmsLeft((n) => Math.max(0, n - 1)), 1000);
    return () => clearTimeout(id);
  }, [smsLeft]);

  /**
   * ⚠️ **软键盘会把这一段整个压在底下,而滚动区已经滚不动了。**
   * 真浏览器量出来:滚动区 clientH 460 / scrollH 610 ⇒ maxScroll 只有 150;
   * 而键盘高 188、上缘落在 y=412(带中文候选条时 246 / 上缘 354)——
   * 两个输入框滚到底时都在 412 以下。键盘自己那句 `scrollIntoView` 需要 scrollTop≈294,
   * 比 maxScroll 还大,救不回来。
   *
   * ⇒ 聚焦时给滚动区垫一段等于键盘高度的下内衬,**不动版式**:不重排段序、不改任何
   * 画出来的元素,四图仍然逐像素可比。键盘没加载(`.skbd` 不存在)时垫 0 —— 那就是没有键盘。
   */
  useEffect(() => {
    const zone = document.querySelector<HTMLElement>('.kiosk-layout-b .kiosk-side__scroll');
    if (!zone) return undefined;
    const inZone = (el: EventTarget | null) =>
      el instanceof HTMLElement && el.tagName === 'INPUT' && zone.contains(el);

    const onFocus = (e: FocusEvent) => {
      if (!inZone(e.target)) return;
      const el = e.target as HTMLElement;
      // 键盘挂在 body 上、在**缩放画布外面**,所以它量出来的 px 是屏幕 px,
      // 而内衬要写进画布坐标 —— 得先除以画布的缩放比。
      requestAnimationFrame(() => {
        const keyboardPx = document.querySelector<HTMLElement>('.skbd')?.offsetHeight ?? 0;
        const canvasW = document.querySelector<HTMLElement>('.kiosk-screen')?.getBoundingClientRect().width;
        const scale = canvasW && canvasW > 0 ? canvasW / 1024 : 1;
        zone.style.paddingBottom = `${Math.round(keyboardPx / scale)}px`;
        el.scrollIntoView({ block: 'center' });
      });
    };
    const onBlur = (e: FocusEvent) => {
      if (!inZone(e.target)) return;
      setTimeout(() => {
        if (!inZone(document.activeElement)) zone.style.paddingBottom = '';
      }, 150);
    };
    zone.addEventListener('focusin', onFocus);
    zone.addEventListener('focusout', onBlur);
    return () => {
      zone.removeEventListener('focusin', onFocus);
      zone.removeEventListener('focusout', onBlur);
      zone.style.paddingBottom = '';
    };
  }, []);

  /** 登录段的目标:点过谁就是谁;没点过就取显示顺序里第一个「可登录且未连接」的。 */
  const loginTarget = useMemo(() => {
    const openOnes = platforms.filter((p) => canLogIn(p.platform) && !p.connected);
    if (picked && openOnes.some((p) => p.platform === picked)) return picked;
    return openOnes[0]?.platform ?? null;
  }, [platforms, picked]);

  const targetMeta = loginTarget ? PLATFORM_META[loginTarget] : undefined;
  const isSms = targetMeta?.login?.passLabel === 'Verification Code';

  const pickForLogin = (platform: string) => {
    setPicked(platform);
    setForm({ user: '', pass: '' });
    setLoginError('');
    setSmsLeft(0);
    requestAnimationFrame(() => loginSectionRef.current?.scrollIntoView({ block: 'nearest' }));
  };

  const sendSms = async () => {
    if (!loginTarget || !token) return;
    if (!form.user.trim()) { setLoginError(t('platform:need_phone', '请先输入手机号')); return; }
    setSmsBusy(true);
    setLoginError('');
    try {
      await API.platformSmsRequest(loginTarget, form.user, token);
      setSmsLeft(60);
    } catch (e) {
      setLoginError(e instanceof Error ? e.message : t('platform:sms_failed', '验证码没发出去'));
    } finally {
      setSmsBusy(false);
    }
  };

  const submitLogin = async () => {
    if (!loginTarget || !token) return;
    setLoginBusy(true);
    setLoginError('');
    try {
      await API.platformLogin(
        loginTarget,
        isSms ? { username: form.user, sms_code: form.pass } : { username: form.user, password: form.pass },
        token,
      );
      setForm({ user: '', pass: '' });
      setPicked(null);
      await refresh();
    } catch (e) {
      setLoginError(e instanceof Error ? e.message : t('platform:login_failed', '登录失败'));
    } finally {
      setLoginBusy(false);
    }
  };

  const doLogout = async (platform: string) => {
    setLogoutTarget(null);
    if (!token) return;
    try {
      await API.platformLogout(platform, token);
      await refresh();
    } catch {
      /* 断开失败时状态由下一次 refresh 说了算,不在屏上编一个「已断开」 */
    }
  };

  const capsOf = (p: PlatformInfo) => [
    [p.supports_live_play, t('platform:cap_live', '实时对弈')],
    [p.supports_automatch, t('platform:cap_automatch', '自动匹配')],
    [p.supports_rooms, t('platform:cap_rooms', '房间')],
    [p.supports_engine_play, t('platform:cap_engine', '人机对弈')],
  ] as const;

  return (
    <div className="kiosk-layout-b plat-layout" data-testid="platform-connect-page">
      <KioskPagebar
        backLabel={t('Back to play', '返回对弈')}
        onBack={() => navigate('/kiosk/play')}
        title={t('Cross-Platform Play', '跨平台对弈')}
        sub={t('platform:connect_sub', '连上外面的围棋平台，用这块实体盘下')}
      />

      <KioskScrollZone>
        <section className="kiosk-section">
          <KioskSecLabel zh={t('platform:platforms', '平台')} en="Platforms" />
          <div className="kiosk-rows">
            {platforms.map((p) => {
              const meta = PLATFORM_META[p.platform] ?? { label: p.platform, labelCn: p.platform, color: '#888' };
              const name = t(meta.label, meta.labelCn);
              return (
                <div className="kiosk-row kiosk-row--caps" key={p.platform} data-testid="platform-row">
                  <span className={`av${p.connected ? '' : ' dim'}`} aria-hidden="true">{name.slice(0, 1)}</span>
                  <div className="kiosk-row__t">
                    <b>{name}</b>
                    {/* 四个标**逐家不同**,照 `/platforms` 原样渲染 —— 前端不修正、不补齐。 */}
                    <span className="caps">
                      {capsOf(p).map(([on, label]) => (
                        <span key={String(label)} className={on ? 'on' : undefined}>{label}</span>
                      ))}
                    </span>
                  </div>
                  <div className="kiosk-row__end">
                    {meta.comingSoon ? (
                      <span className="kiosk-tag kiosk-tag--warn">{t('platform:no_play_yet', '暂不能对弈')}</span>
                    ) : p.connected ? (
                      <>
                        {/* 共用终端上「现在连的是谁的号」是按下登出之前必须看得见的事实。
                            拿不到用户名就只写「已连接」,不编。 */}
                        <span className="kiosk-tag kiosk-tag--win">
                          {p.saved_username
                            ? `${t('platform:connected', '已连接')} · ${p.saved_username}`
                            : t('platform:connected', '已连接')}
                        </span>
                        <button
                          type="button"
                          className="kiosk-btn kiosk-btn--pill"
                          data-testid="platform-logout"
                          onClick={() => setLogoutTarget(p.platform)}
                        >{t('platform:logout', '登出')}</button>
                        <button
                          type="button"
                          className="kiosk-btn kiosk-btn--pill"
                          onClick={() => navigate(p.supports_engine_play
                            ? `/kiosk/play/cross-platform/engine/${p.platform}`
                            : `/kiosk/play/cross-platform/lobby?platform=${p.platform}`)}
                        >
                          {p.supports_engine_play
                            ? t('platform:enter_engine', '人机对弈')
                            : t('platform:enter_lobby', '进入大厅')}
                        </button>
                      </>
                    ) : (
                      <>
                        <span className="kiosk-tag">{t('platform:disconnected', '未连接')}</span>
                        <button
                          type="button"
                          className="kiosk-btn kiosk-btn--pill"
                          data-testid="platform-login"
                          onClick={() => pickForLogin(p.platform)}
                        >{t('Login', '登录')}</button>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
            {!loaded && <p className="lobbyempty">{t('lobby:loading', '正在读…')}</p>}
          </div>
        </section>

        <section className="kiosk-section">
          <KioskSecLabel zh={t('platform:what_you_get', '连上之后')} en="What you get" />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="av" aria-hidden="true">{t('platform:icon_board', '盘')}</span>
              <div className="kiosk-row__t">
                <b>{t('platform:get_board', '用这块实体盘下')}</b>
                <em>{t('platform:get_board_sub', '摆子就是落子，对面看到的是同一手')}</em>
              </div>
            </div>
            <div className="kiosk-row">
              <span className="av" aria-hidden="true">{t('platform:icon_kifu', '谱')}</span>
              <div className="kiosk-row__t">
                <b>{t('platform:get_kifu', '下完自动存谱')}</b>
                <em>{t('platform:get_kifu_sub', '进棋谱库，也能送去复盘')}</em>
              </div>
            </div>
            <div className="kiosk-row">
              <span className="av" aria-hidden="true">{t('platform:icon_rank', '分')}</span>
              <div className="kiosk-row__t">
                <b>{t('platform:get_rank', '盒内段位不受影响')}</b>
                <em>{t('platform:get_rank_sub', '那边的胜负只进那边的账')}</em>
              </div>
            </div>
          </div>
        </section>

        {/* 三家全连上 ⇒ 这一段整个不渲染。行本身每一行都写着「已连接」,那就是答案。 */}
        {loginTarget && targetMeta?.login && (
          <section
            className="kiosk-section"
            data-testid="platform-login-section"
            ref={loginSectionRef}
          >
            <KioskSecLabel
              zh={interpolate(t('platform:sign_in_to', '登录 · {name}'), { name: t(targetMeta.label, targetMeta.labelCn) })}
              en="Sign in"
              value={isSms
                ? t('platform:sms_fields', '手机号 + 验证码')
                : t('platform:pw_fields', '用户名 + 密码')}
            />
            <div className="kiosk-rows">
              <div className="kiosk-row">
                <span className="kiosk-row__lead">
                  {t(targetMeta.login.userLabel, targetMeta.login.userLabelCn)}
                </span>
                <div className="kiosk-row__t">
                  <em>{isSms
                    ? t('platform:phone_note', '只用来向平台换一个登录凭证')
                    : t('platform:user_note', '那边的账号名，不是盒子的账号')}</em>
                </div>
                <div className="kiosk-row__end">
                  <input
                    className="nameinput nameinput--search"
                    data-testid="platform-login-user"
                    type={targetMeta.login.userType === 'tel' ? 'tel' : 'text'}
                    aria-label={t(targetMeta.login.userLabel, targetMeta.login.userLabelCn)}
                    placeholder={t('local:tap_to_type', '点此输入')}
                    value={form.user}
                    onChange={(e) => setForm((f) => ({ ...f, user: e.target.value }))}
                  />
                </div>
              </div>
              <div className="kiosk-row">
                <span className="kiosk-row__lead">
                  {t(targetMeta.login.passLabel, targetMeta.login.passLabelCn)}
                </span>
                <div className="kiosk-row__t">
                  <em>{isSms
                    ? t('platform:code_note', '六位数字 · 60 秒内有效')
                    : t('platform:pw_note', '只发给那个平台，不存在盒子上')}</em>
                </div>
                <div className="kiosk-row__end">
                  {isSms && (
                    <button
                      type="button"
                      className="kiosk-btn kiosk-btn--pill"
                      data-testid="platform-sms"
                      disabled={smsBusy || smsLeft > 0}
                      onClick={() => { void sendSms(); }}
                    >
                      {smsLeft > 0
                        ? interpolate(t('platform:sms_again', '{n} 秒后可重发'), { n: smsLeft })
                        : t('platform:sms_get', '获取验证码')}
                    </button>
                  )}
                  <input
                    className="nameinput nameinput--search"
                    data-testid="platform-login-pass"
                    type={isSms ? 'text' : 'password'}
                    aria-label={t(targetMeta.login.passLabel, targetMeta.login.passLabelCn)}
                    placeholder={t('local:tap_to_type', '点此输入')}
                    value={form.pass}
                    onChange={(e) => setForm((f) => ({ ...f, pass: e.target.value }))}
                    onKeyDown={(e) => { if (e.key === 'Enter') void submitLogin(); }}
                  />
                </div>
              </div>
            </div>
            {/* 登录出错要有落点 —— 没有落点的错误等于没报错。 */}
            {loginError && <p className="loginerr" data-testid="platform-login-error">{loginError}</p>}
            <button
              type="button"
              className="kiosk-btn kiosk-btn--secondary loginsubmit"
              data-testid="platform-login-submit"
              disabled={loginBusy}
              onClick={() => { void submitLogin(); }}
            >
              {loginBusy ? t('platform:logging_in', '正在登录…') : t('Login', '登录')}
            </button>
          </section>
        )}
      </KioskScrollZone>

      {/* 登出确认。它离「进入大厅」只有 10px,误触在星阵那家的代价是重走一遍短信。 */}
      {logoutTarget && (
        <div className="cdlg" data-testid="platform-logout-confirm">
          <div className="cdlg__box wdlg" role="dialog" aria-modal="true">
            <h3>{interpolate(
              t('platform:logout_ask', '断开 {name}？'),
              { name: t(PLATFORM_META[logoutTarget]?.label ?? logoutTarget, PLATFORM_META[logoutTarget]?.labelCn ?? logoutTarget) },
            )}</h3>
            <p className="wdlg__lead">{t('platform:logout_body', '这台盒子上就不再是这个号了。再进去要重新登录一次。')}</p>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={() => setLogoutTarget(null)}>
                {t('cancel', '取消')}
              </button>
              <button
                type="button"
                className="main"
                data-testid="platform-logout-confirm-action"
                onClick={() => { void doLogout(logoutTarget); }}
              >{t('platform:logout', '登出')}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default PlatformConnectPage;
