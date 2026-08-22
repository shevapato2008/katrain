import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from '../../hooks/useTranslation';
import { useAuth } from '../../context/AuthContext';
import { readActiveSession } from '../utils/activeSession';
import { API, type PlatformInfo } from '../../api';
import { PLATFORM_META } from '../constants/platforms';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { KioskCard } from '../shell/KioskCard';
import type { IconName } from '../shell/icons';

// 顺序照稿子:**能用的排前面,「即将上线」排最后**。上一版是 ogs/fox/golaxy,
// 于是连不上的野狐夹在两个能用的中间 —— 一排卡里最先撞见的是那张按不动的。
const PLATFORM_CATALOGUE = ['ogs', 'golaxy', 'fox'] as const;

// 稿子给每个平台配的图标(`go-kiosk.tmpl.html:play`):星阵是引擎直连,画机器人;
// 走大厅的画地球。图标不带语义色,状态由 `.dot` / `.soon` 表达。
const PLATFORM_ICON: Record<string, IconName> = {
  ogs: 'globe-hemisphere-west',
  fox: 'globe-hemisphere-west',
  golaxy: 'robot',
};

const defaultPlatforms = (): PlatformInfo[] => PLATFORM_CATALOGUE.map((platform) => ({
  platform,
  connected: false,
  supports_live_play: false,
  supports_automatch: false,
  supports_rooms: false,
  supports_seek_graph: false,
  supports_engine_play: false,
}));

const mergePlatformStatus = (records: PlatformInfo[]): PlatformInfo[] => {
  const byPlatform = new Map(records.map((record) => [record.platform, record]));
  return defaultPlatforms().map((fallback) => byPlatform.get(fallback.platform) ?? fallback);
};

/**
 * 屏 01 · 对弈首页 `/kiosk/play` —— L1 布局 A(镜像栏 296 + 16 + 右栏 680)。
 *
 * 这一屏**只回答「下哪一种」**:落子方式(屏幕 / 实体盘)和棋盘路数已经下沉到各自的开局设置屏,
 * 不在这儿问。左边那条镜像栏由 `KioskLayout` 渲染(`GoConsoleRail`),本文件只管右栏。
 *
 * 结构逐节对着稿子 `sample-go/go-kiosk.tmpl.html` 的 `data-screen="play"`:
 * 问候 → 继续上一局 → 人机对弈 → 人人对弈 → 跨平台对弈 → 对局历史,
 * 五块都是 `.kiosk-side__scroll` 的直接子元素,块间距由它的 `--l1-section-gap` 给。
 *
 * **稿子上那两条 `.secval` 没搬**(「强度档说的是对手,不是你的段位」「平台由 /platforms 返回」):
 * `.secval` 的位置按规范放的是**数据**,而这两句是写给读稿人的解释(G5)。三家一处旁注都没搬。
 *
 * **「全部对局」那张卡的副标没有数字。** 稿子写的是「6 局 · 1 局已有报告」—— 那是稿子上的
 * 示例数据,本页拿不到真数(要另开一次 `user-games` 计数请求)。**不许把示例数字当成真的印上去**,
 * 所以写成一句不含数字的实话。要数字就得先去取,已登记。
 */
const PlayPage = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const resume = readActiveSession('game');
  const [platforms, setPlatforms] = useState<PlatformInfo[]>(defaultPlatforms);

  useEffect(() => {
    let current = true;
    setPlatforms(defaultPlatforms());

    if (token) {
      API.platformStatus(token).then((d) => {
        if (current) setPlatforms(mergePlatformStatus(d.platforms));
      }).catch(() => {
        if (current) setPlatforms(defaultPlatforms());
      });
    }

    return () => { current = false; };
  }, [token]);

  const hour = new Date().getHours();
  const [greetKey, greetZh] =
    hour < 6 ? ['Late night', '夜深了'] :
    hour < 11 ? ['Good morning', '早上好'] :
    hour < 13 ? ['Good noon', '中午好'] :
    hour < 18 ? ['Good afternoon', '下午好'] :
    ['Good evening', '晚上好'];

  return (
    <KioskScrollZone>
      <div className="kiosk-greet">
        <b>
          {t(greetKey, greetZh)}
          {user?.username && <>，<i>{user.username}</i></>}
        </b>
        <span>{t('Choose a way to start playing', '选择一种方式开始对弈')}</span>
      </div>

      {resume && (
        <div className="kiosk-resume" data-testid="resume-game-bar">
          <span className="bar" />
          <div>
            <h4>{t('Resume last game', '继续上一局')}</h4>
            <p>{resume.label}</p>
          </div>
          <button
            type="button"
            className="kiosk-btn kiosk-btn--pill pill"
            onClick={() => navigate(resume.route)}
          >
            {t('Resume', '恢复')}
          </button>
        </div>
      )}

      <section className="kiosk-section">
        <KioskSecLabel zh={t('Play vs AI', '人机对弈')} en="vs KataGo" />
        <div className="kiosk-cards">
          <KioskCard
            title={t('Free Game', '自由对弈')}
            sub={t('Pick the strength yourself · form estimate available', '自己挑强度 · 可以看形势判断')}
            icon="robot"
            onClick={() => navigate('/kiosk/play/ai/setup/free')}
          />
          <KioskCard
            title={t('Ranked Game', '升降级对弈')}
            sub={t('Tier picked from your strength · analysis sealed throughout', '按棋力自动配档 · 全程封分析')}
            icon="trophy"
            onClick={() => navigate('/kiosk/play/ai/setup/ranked')}
          />
        </div>
      </section>

      <section className="kiosk-section">
        <KioskSecLabel zh={t('Play vs Human', '人人对弈')} en="vs Human" />
        <div className="kiosk-cards">
          <KioskCard
            title={t('Local Game', '本地对局')}
            sub={t('Two players on the same physical board', '两人在同一块实体盘上下')}
            icon="users"
            onClick={() => navigate('/kiosk/play/pvp/setup')}
          />
          <KioskCard
            title={t('Online Lobby', '在线大厅')}
            sub={t('Challenge others · rated queue available', '约战 · 有定级队列')}
            icon="globe-hemisphere-west"
            onClick={() => navigate('/kiosk/play/pvp/lobby')}
          />
        </div>
      </section>

      <section className="kiosk-section">
        <KioskSecLabel zh={t('Cross-Platform', '跨平台对弈')} en="Cross-platform" />
        <div className="kiosk-cards">
          {platforms.map((p) => {
            const meta = PLATFORM_META[p.platform] ?? { label: p.platform, labelCn: p.platform, color: '#888' };
            // 「即将上线」不是「锁定」:锁定意味着东西在、满足条件就给。接口没通的平台
            // 不许摆成锁着的样子 —— `comingSoon` 是 PLATFORM_META 里就有的真标记,不是这里现编的。
            if (meta.comingSoon) {
              return (
                <KioskCard
                  key={p.platform}
                  title={t(meta.label, meta.labelCn)}
                  sub={t('Not wired up yet', '接口还没通')}
                  icon={PLATFORM_ICON[p.platform] ?? 'globe-hemisphere-west'}
                  soon={t('Coming soon', '即将上线')}
                />
              );
            }
            const target = p.connected
              ? (p.supports_engine_play
                  ? `/kiosk/play/cross-platform/engine/${p.platform}`
                  : `/kiosk/play/cross-platform/lobby?platform=${p.platform}`)
              : '/kiosk/play/cross-platform';
            // 副标说的是**下一步会发生什么**,而且每一句都从真状态推出来:
            // 连上了就说走哪条路,没连上就说这个平台要拿什么登录(登录字段在 PLATFORM_META 里)。
            const sub = p.connected
              ? (p.supports_engine_play
                  ? t('Connected · plays the engine', '已连接 · 人机对弈')
                  : t('Connected · goes to the lobby', '已连接 · 走大厅'))
              : meta.login
                ? `${t('Tap to connect', '点击登录')} · ${t(meta.login.userLabel, meta.login.userLabelCn)} + ${t(meta.login.passLabel, meta.login.passLabelCn)}`
                : t('Tap to connect', '点击登录');
            return (
              <KioskCard
                key={p.platform}
                title={t(meta.label, meta.labelCn)}
                sub={sub}
                icon={PLATFORM_ICON[p.platform] ?? 'globe-hemisphere-west'}
                dot={p.connected}
                onClick={() => navigate(target)}
              />
            );
          })}
        </div>
      </section>

      <section className="kiosk-section">
        <KioskSecLabel zh={t('Game History', '对局历史')} en="History" />
        <div className="kiosk-cards">
          <KioskCard
            title={t('All games', '全部对局')}
            sub={t('Every game played, with its review report', '下过的每一局,连同它的复盘报告')}
            icon="grid-nine"
            onClick={() => navigate('/kiosk/report')}
          />
        </div>
      </section>
    </KioskScrollZone>
  );
};

export default PlayPage;
