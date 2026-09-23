import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API, type PlatformInfo } from '../../api';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { useKeyboardInset } from '../hooks/useKeyboardInset';
import { PLATFORM_META, defaultPlatforms, mergePlatformStatus } from '../constants/platforms';
import { interpolate } from '../utils/interpolate';

/**
 * 屏 07 跨平台 · 连接(`sample-go/shots/07-platform.png`,L2 布局 B)。
 *
 * 首页「跨平台对弈」那三张卡未连接时全都落到这儿。两件事必须画对,少一件这一屏就白画了:
 *
 * ① **每家支持什么不一样**,四个能力标由 `/platforms` 下发,不是界面写死的四个格子。
 *    亮着的才是那一家真支持的。
 * ② **已连接的那家进的是大厅还是人机开局**,取决于 `supports_engine_play` ——
 *    星阵能给的对手是那 39 档 bot 不是人(`get_online_users` 直接 `return []`),
 *    所以它进人机开局;OGS 进大厅。
 *
 * ## 2026-09-23(Task 5):登录改成独立成页
 *
 * 原来这一屏有一段页内登录表单(2026-08-24 裁定,判例是屏 04 的「点此输入」药丸:
 * 「静态稿只能画到药丸这一步,真页面上它必须真能输入……不做『点药丸弹一个输入框』」)。
 * 这一版把登录段整段撤掉,「登录」按钮改成跳 `PlatformLoginPage`
 * (`/kiosk/play/cross-platform/login/:platform`)—— 星阵已经有验证码/密码两条真路,
 * 摆进一段折叠在连接页里的表单反而挤;独立成页之后每家还能各自长出扫码(Task 6)。
 * 「不做弹层」那条判例仍然成立,只是「页内一段」换成了「独立一页」,两者都不是弹层。
 *
 * ## 其余仍按 2026-08-24 的裁定落的
 *
 * **登出留在行尾,而且要有字。** 稿子那一行只有「已连接」+「进入大厅」,这一处是
 * **实现反过来纠正稿子**:登出是业务动作,规范 §11 明写「悔棋、认输、求和、提示这些
 * 业务动作一律不许上页控条」;行尾也不挤:这一屏是布局 B 通栏 992,能力标右缘到行尾之间
 * 空着 545px。误触的代价在星阵那家是重走一遍短信,所以走一次确认弹层
 * (和屏 08 的「挑战」同一条规矩)。
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
 */

const PlatformConnectPage = () => {
  const { t } = useTranslation();
  // token 只当**凭据**用（严格盒端恒为 null，身份在 HttpOnly sb_go_token cookie 里）；
  // 「认没认证」一律判 isAuthenticated —— 判 token 会让盒上每个已登录用户都进不来。
  const { token, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [platforms, setPlatforms] = useState<PlatformInfo[]>(defaultPlatforms);
  const [loaded, setLoaded] = useState(false);
  const [logoutTarget, setLogoutTarget] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!isAuthenticated) { setLoaded(true); return; }
    try {
      const data = await API.platformStatus(token);
      setPlatforms(mergePlatformStatus(data.platforms));
    } catch {
      // 问不到就摆一份全 false 的:能力标全暗、行尾只给登录。**不伪造乐观默认。**
      setPlatforms(defaultPlatforms());
    } finally {
      setLoaded(true);
    }
  }, [isAuthenticated, token]);

  useEffect(() => { void refresh(); }, [refresh]);

  // 软键盘避让 —— 逻辑与注释见 `useKeyboardInset` 头注(2026-09-23 从这里提成共享 hook,
  // 登录页 `PlatformLoginPage` 也用它)。这一屏的滚动容器是 `.kiosk-layout-b .kiosk-side__scroll`。
  useKeyboardInset('.kiosk-layout-b .kiosk-side__scroll');

  const doLogout = async (platform: string) => {
    setLogoutTarget(null);
    if (!isAuthenticated) return;
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
                          onClick={() => navigate(`/kiosk/play/cross-platform/login/${p.platform}`)}
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
