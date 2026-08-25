import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router-dom';

import { useSettings } from '../../context/SettingsContext';
import { useGeometry } from '../context/GeometryContext';
import { useTranslation } from '../../hooks/useTranslation';
import AccountSection from '../components/settings/AccountSection';
import { PLATFORM_META } from '../constants/platforms';
import { Icon, type IconName } from '../shell/icons';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { readAudioPref, subscribeAudioPref, writeAudioPref, type AudioKind } from '../../utils/audioPrefs';
import { readAutoAdvance, writeAutoAdvance } from './tsumegoUnits';

/**
 * 屏 27 · 设置 `/kiosk/settings` —— **L1-B**:左栏仍是 296 的 `.kiosk-console`,
 * 装的却是导航不是盘(规范 §12:左栏宽度和 L1-A 的镜像栏一样,
 * **从对弈切到设置那条纵向接缝不动**)。
 *
 * ## 只做有内容的组(计划 D10 方案 a)
 *
 * 稿子摆了七组,而这台盒子上**五组没有内容**。三条路里选的是「只做有内容的」:
 *   · 七组全摆、空的挂琥珀「未接后端」—— **是用错标**:那五组大部分不是「后端没有」,
 *     而是「这个设置项还没做」。两回事,两种颜色。
 *   · 七组全摆、空的做成真功能 —— 那是五个新 feature,远超一条表现层赛道。
 * ⇒ **导航项数 = 分组数,且词一一对应**。导航里写「实体棋盘」,右边那组的标题就是「实体棋盘」——
 * 两套词等于两套心智模型。差异图上因此少三组,这是**裁定不是遗漏**。
 *
 * ## 导航只跳不换页,高亮跟着真正在看的那一组走
 *
 * 点导航是**滚过去**,不是把右边整块换掉 —— 换页式在这块屏上更差:
 * 用户看不到自己一共有多少可调的。
 * 而高亮**写死在某一项上、右边却滚到了别处,是在谎报你在哪儿** ——
 * 所以它跟着滚动位置算,不跟着最后点过哪一项。
 *
 * ## 账号那两行也是 `.kiosk-row`
 *
 * 上一版 `AccountSection` 是一张 MUI 卡 + 一条满宽的红色退出按钮,夹在两组行中间
 * **像是从别的应用里剪进来的**。2026-08-23 重排成两行:一行账号,一行 AI 段位。
 * 段位详情那张卡(`AiLadderStatusCard`)还没重画 —— 它只在点开对话框之后才出现。
 *
 * ## 语言这一组是规范 §12 的一处**已知偏差**
 *
 * 规范明写「系统设置(网络、账号、**语言**、输入法)不在这里,在设置中心」。
 * 但**设置中心不在本仓** —— 搬走等于这台盒子上再没有语言开关。
 * ⇒ 留着,登记为已知偏差,等设置中心接手。
 *
 * ## 页控条撤了
 *
 * 设置是 Dock 项 ⇒ L1。**L1 没有返回键** —— 要退的是「回哪儿」,而 Dock 一直在。
 * 上一版那条页控条(带返回 + `location.state.from`)是它还是 L2 时留下的。
 */

type GroupKey = 'account' | 'board' | 'move' | 'sound' | 'language';

const GROUPS: readonly { key: GroupKey; zh: string; en: string; icon: IconName }[] = [
  { key: 'account', zh: '账号与平台', en: 'Account', icon: 'user-circle' },
  { key: 'board', zh: '实体棋盘', en: 'Physical board', icon: 'camera' },
  { key: 'move', zh: '落子与提示', en: 'Move & hints', icon: 'hand-pointing' },
  // 稿子这一组叫「声音与报着」。**这里只写「声音」** —— 盒子上没有报着:
  // `useVoice` 说的是摆子引导那七句(清盘 / 摆黑子 / 对了 …),不是报手数。
  // 词跟着屏上真有的东西走,多写两个字就是承诺一个不存在的功能(见本文件顶上那条
  // 「导航里写什么,右边那组的标题就是什么」)。
  { key: 'sound', zh: '声音', en: 'Sound', icon: 'speaker-high' },
  { key: 'language', zh: '语言', en: 'Language', icon: 'globe-hemisphere-west' },
];

/**
 * 两把开关,**分开**:音效是几十毫秒的一声,引导语是一整句话 ——
 * 教室里最先想关掉的往往是后者,合成一把就逼人连落子声一起丢掉。
 */
const AUDIO_ROWS: readonly {
  kind: AudioKind; titleKey: string; title: string; subKey: string; sub: string;
}[] = [
  {
    kind: 'sfx',
    titleKey: 'settings:sound_sfx', title: '落子音效',
    subKey: 'settings:sound_sfx_sub', sub: '落子、提子、做题对错 · 出厂就是开的',
  },
  {
    kind: 'voice',
    titleKey: 'settings:sound_voice', title: '语音提示',
    // 照实说它什么时候会响:这台盒子没接摄像头的话它一次都不会响,
    // 而屏上写「开」而永远不响,用户会以为坏了。
    subKey: 'settings:sound_voice_sub', sub: '摆棋和做题时的引导语 · 只在用实体棋盘时会响',
  },
];

const SettingsPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { language, setLanguage, languages } = useSettings();
  const { status } = useGeometry();
  const [autoAdvance, setAutoAdvance] = useState(() => readAutoAdvance());
  const [active, setActive] = useState<GroupKey>(GROUPS[0].key);
  const [scrollEl, setScrollEl] = useState<HTMLElement | null>(null);
  const [tail, setTail] = useState(0);

  // 滚动容器归 `KioskScrollZone` 拿着 —— 从第一组往上找一次就够,不去动那个共享件。
  const anchorRef = useCallback((el: HTMLElement | null) => {
    setScrollEl((el?.closest('.kiosk-side__scroll') as HTMLElement) ?? null);
  }, []);

  /**
   * 尾部留白。**不是排版留白,是让高亮说得出真话的前提**:
   * 最后一组只有 78 高,而视口是 434 —— 滚到底它的上缘离视口顶还差 300 多,
   * 「滚过视口顶的那一组就是正在看的」这条规则**永远轮不到它**。
   * 于是点导航第 3 项之后,scroll 事件会把高亮弹回第 2 项 —— 那才是「谎报你在哪儿」。
   * 补一段 `视口高 − 最后一组高` 的空,每一组就都能滚到顶上。
   *
   * 量在**最后一组的 callback ref** 里,不在 effect 里:effect 里同步 setState 会被
   * `react-hooks/set-state-in-effect` 拦下,而 ref 回调本来就是「元素到位了」的那一刻。
   */
  const lastGroupRef = useCallback((el: HTMLElement | null) => {
    const scroll = el?.closest('.kiosk-side__scroll');
    if (!el || !scroll) return;
    const need = Math.max(0, scroll.clientHeight - el.getBoundingClientRect().height);
    setTail((current) => (Math.abs(current - need) < 1 ? current : need));
  }, []);

  useEffect(() => {
    if (!scrollEl) return;
    const onScroll = () => {
      const top = scrollEl.getBoundingClientRect().top;
      let current = GROUPS[0].key;
      for (const g of GROUPS) {
        const el = scrollEl.querySelector(`[data-group="${g.key}"]`);
        // 上缘已经滚过视口顶(留 8px 容差)的那一组就是「正在看的」——
        // 最后一组永远排在后面,所以循环到底自然取到最靠下的那一个。
        if (el && el.getBoundingClientRect().top - top <= 8) current = g.key;
      }
      setActive(current);
    };
    scrollEl.addEventListener('scroll', onScroll, { passive: true });
    return () => scrollEl.removeEventListener('scroll', onScroll);
  }, [scrollEl]);

  const jumpTo = (key: GroupKey) => {
    // ⚠️ 这里**从 DOM 现查**,不用上面那个 `scrollEl` 状态 —— `react-hooks/immutability`
    // 会把「改 useState 拿到的那个值的 scrollTop」当成直接改状态。滚动位置是 DOM 的属性,
    // 不是 React 状态,可那条规则分不出来;现查一次既躲开它,也不多一份真相。
    const el = document.querySelector(`[data-group="${key}"]`);
    const scroll = el?.closest('.kiosk-side__scroll');
    if (!el || !scroll) return;
    // 不用 `scrollIntoView`:它会把**整个 kiosk 画布**也一起滚(祖先链上还有别的滚动容器),
    // 而这块画布是固定 1024×600 的,一滚就露边。
    scroll.scrollTop += el.getBoundingClientRect().top - scroll.getBoundingClientRect().top;
    setActive(key);
  };

  // 两把声音开关读的是 `utils/audioPrefs` 那一份模块级状态,**不另存一份 useState** ——
  // 两份迟早走散,而走散的表现正好是「屏上写着关、喇叭还在响」。
  const sfxOn = useSyncExternalStore(subscribeAudioPref, () => readAudioPref('sfx'), () => true);
  const voiceOn = useSyncExternalStore(subscribeAudioPref, () => readAudioPref('voice'), () => true);

  const handleAutoAdvance = (next: boolean) => {
    setAutoAdvance(next);
    writeAutoAdvance(next);
  };

  const calibratedAt = status.session_calibrated
    ? t('settings:calibrated', '这次开机已标定')
    : t('settings:not_calibrated', '还没标定');

  return (
    <div className="kiosk-layout-l1" data-testid="settings-page">
      <aside className="kiosk-console">
        <div className="kiosk-console__title">
          <b>{t('Settings', '设置')}</b><em>Settings</em>
        </div>
        <nav className="kiosk-navlist" data-testid="settings-nav" aria-label={t('Settings', '设置')}>
          {GROUPS.map((g) => (
            <button
              key={g.key}
              type="button"
              className="kiosk-navitem"
              aria-current={active === g.key}
              onClick={() => jumpTo(g.key)}
            >
              <Icon name={g.icon} />{t(`settings:nav_${g.key}`, g.zh)}
            </button>
          ))}
        </nav>
      </aside>

      <KioskScrollZone>
        <section className="kiosk-section" data-group="account" ref={anchorRef}>
          <KioskSecLabel zh={t('settings:nav_account', '账号与平台')} en="Account" />
          <p className="setnote">
            {t('settings:box_account_sub', '不登录也能用，成绩存在这台盒子上；登录只是为了换机器时能带走')}
          </p>
          <div className="kiosk-rows">
            {/* 账号那两行(账号 + AI 段位)在 `AccountSection` 里,和下面那行是同一族 `.kiosk-row`。
                ⚠️ **段位详情那张卡还没重画** —— 它只在点开对话框之后才出现,不占这一组的正面。 */}
            <AccountSection />
            {/* 上一版这儿摆着四张 `pointer-events:none` 的死卡,列的是 99围棋/野狐/腾讯/新浪 ——
                **和真正能连的三家对不上**。改成一行真入口:连哪一家、怎么连,都在跨平台对弈那条路上,
                三家的登录字段还各不相同,不该在这儿复制一套表单。 */}
            <div className="kiosk-row">
              <span className="kiosk-row__t">
                <b>{t('settings:platforms', '跨平台账号')}</b>
                <em>
                  {Object.values(PLATFORM_META).map((p) => p.labelCn).join(' · ')}
                  {' · '}
                  {t('settings:platforms_sub', '各家登录字段不同，在跨平台对弈里连')}
                </em>
              </span>
              <span className="kiosk-row__end">
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--secondary"
                  onClick={() => navigate('/kiosk/play/cross-platform')}
                >
                  {t('settings:go_connect', '去连接')}
                </button>
              </span>
            </div>
          </div>
        </section>

        <section className="kiosk-section" data-group="board">
          <KioskSecLabel
            zh={t('settings:nav_board', '实体棋盘')}
            en="Physical board"
            value={t('settings:board_secval', '摄像头 · 标定 · LED')}
          />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="kiosk-row__t">
                <b>{t('Recalibrate board', '重新标定棋盘')}</b>
                <em>{calibratedAt}</em>
              </span>
              <span className="kiosk-row__end">
                <button
                  type="button"
                  className="kiosk-btn kiosk-btn--secondary"
                  onClick={() => navigate('/kiosk/vision/setup')}
                >
                  {t('settings:start_calib', '开始标定')}
                </button>
              </span>
            </div>
            {/* 三件器件的读数。**「读不到」和「没连上」是两回事** ——
                `capabilities` 里没有那一项时不点灯,不拿一颗灰灯冒充「未连接」。 */}
            {([
              ['camera', t('Camera', '摄像头'), status.capabilities.camera_ready],
              ['calib', t('Calibration', '几何标定'), status.capabilities.geometry_ready],
              ['led', 'LED', status.capabilities.led_ready],
            ] as const).map(([key, label, ok]) => (
              <div className="kiosk-row" key={key} data-testid={`settings-cap-${key}`}>
                <span className="kiosk-row__t"><b>{label}</b></span>
                <span className="kiosk-row__end">
                  <span className={ok ? 'kiosk-tag kiosk-tag--win' : 'kiosk-tag'}>
                    {ok ? t('settings:ready', '就绪') : t('settings:not_ready', '未连接')}
                  </span>
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="kiosk-section" data-group="move">
          <KioskSecLabel zh={t('settings:nav_move', '落子与提示')} en="Move & hints" />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="kiosk-row__t">
                <b>{t('tsumego:autoAdvance', '做对后自动进入下一题')}</b>
                <em>{t('settings:auto_advance_sub', '训练营里生效 · 出厂就是开的')}</em>
              </span>
              <span className="kiosk-row__end">
                {/* 一屏之内所有选择组用**同一种控件**(规范 §12)—— 所以是分段不是开关。 */}
                <span className="kiosk-seg" role="group" aria-label={t('tsumego:autoAdvance', '做对后自动进入下一题')}>
                  <button
                    type="button" className="kiosk-seg__btn" aria-pressed={autoAdvance}
                    onClick={() => handleAutoAdvance(true)}
                  >
                    {t('settings:on', '开')}
                  </button>
                  <button
                    type="button" className="kiosk-seg__btn" aria-pressed={!autoAdvance}
                    onClick={() => handleAutoAdvance(false)}
                  >
                    {t('settings:off', '关')}
                  </button>
                </span>
              </span>
            </div>
          </div>
        </section>

        <section className="kiosk-section" data-group="sound">
          <KioskSecLabel zh={t('settings:nav_sound', '声音')} en="Sound" />
          <div className="kiosk-rows">
            {AUDIO_ROWS.map((row) => (
              <div className="kiosk-row" key={row.kind}>
                <span className="kiosk-row__t">
                  <b>{t(row.titleKey, row.title)}</b>
                  <em>{t(row.subKey, row.sub)}</em>
                </span>
                <span className="kiosk-row__end">
                  {/* 同屏同控件(规范 §12):和「做对后自动进入下一题」一样是分段,不是开关。 */}
                  <span className="kiosk-seg" role="group" aria-label={t(row.titleKey, row.title)}>
                    <button
                      type="button" className="kiosk-seg__btn"
                      aria-pressed={row.kind === 'sfx' ? sfxOn : voiceOn}
                      onClick={() => writeAudioPref(row.kind, true)}
                    >
                      {t('settings:on', '开')}
                    </button>
                    <button
                      type="button" className="kiosk-seg__btn"
                      aria-pressed={!(row.kind === 'sfx' ? sfxOn : voiceOn)}
                      onClick={() => writeAudioPref(row.kind, false)}
                    >
                      {t('settings:off', '关')}
                    </button>
                  </span>
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="kiosk-section" data-group="language" ref={lastGroupRef}>
          <KioskSecLabel zh={t('settings:nav_language', '语言')} en="Language" />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="kiosk-row__t">
                <b>{t('settings:ui_language', '界面语言')}</b>
                {/* 规范 §12 说语言该在设置中心 —— **可设置中心不在本仓**,
                    搬走等于这台盒子上再没有语言开关。屏上照实说它将来会搬。 */}
                <em>{t('settings:language_sub', '这一项将来会搬到设置中心')}</em>
              </span>
              <span className="kiosk-row__end">
                {/* 十一种语言摆不成分段控件(最多三段);用原生 select,不引 MUI 的下拉。 */}
                <select
                  className="ksearch__box"
                  data-testid="settings-language"
                  aria-label={t('settings:ui_language', '界面语言')}
                  value={language}
                  onChange={(e) => { void setLanguage(e.target.value); }}
                >
                  {languages.map((lang) => (
                    <option key={lang.code} value={lang.code}>{lang.name}</option>
                  ))}
                </select>
              </span>
            </div>
          </div>
        </section>
        {tail > 0 && <div aria-hidden="true" data-testid="settings-tail" style={{ height: tail, flex: 'none' }} />}
      </KioskScrollZone>
    </div>
  );
};

export default SettingsPage;
