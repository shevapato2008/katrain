import { useCallback, useEffect, useState } from 'react';
import { Alert, Snackbar } from '@mui/material';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { API, type PlatformUser } from '../../api';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { PLATFORM_META } from '../constants/platforms';
import { interpolate } from '../utils/interpolate';

/**
 * 屏 08 跨平台 · 大厅(`sample-go/shots/08-platform-lobby.png`,L2 布局 B)。
 *
 * 和「在线大厅」(屏 06)长得像但**不是同一屏**:那边是盒子自己的人人对弈,这边是
 * 别人平台上的人。两边的段位是两本账 —— 这一点必须在屏上说出来,否则用户会以为
 * 在 OGS 赢一局盒内段位会动。
 *
 * ## 稿子替这一屏裁掉的两样(照做,理由是仓里的事实)
 *
 * ① **顶上那排「OGS | 星阵围棋」平台分段不画。** 两处都不对:实现里那排 Tabs
 *    `connectedPlatforms.length > 1` 才渲染,真机上一般不出现;更要紧的是**星阵根本
 *    不该出现在这一屏** —— 它的 `get_online_users` / `get_rooms` 都 `return []`
 *    (`platforms/golaxy/adapter.py`、`platforms/base.py`),那边没有可挑战的人的名单。
 *    切过去只会是一张空列表,而**空列表和「这儿本来就没有」长得一模一样**。
 *    ⇒ 这一屏只服务「有人可挑战」的那些平台;星阵那张卡在屏 07 上进的是人机开局。
 * ② **挑战条件不给选。** `platformSendChallenge` 那三项(19 路 / 中国规则 / 计分局)
 *    实现里就是写死的,画成可选项等于承诺一个不存在的开关 ⇒ 摆成一行只读的读数。
 *
 * ## 「自动匹配」只有一颗(2026-08-24 裁定)
 *
 * 稿子把它画了**两处**:搜索那行的行尾一颗次要按钮,再加底下一整段「自动匹配」。
 * 两颗打的是同一个 `platformStartAutomatch`,而这一屏**根本不滚**(三条结果时内容底边
 * y=564 < 586),两颗同屏可见 ⇒ 排队中会同时挂着「取消匹配」和「开始匹配」。
 * **一个状态摆两个地方,必有一个在撒谎。** 删的是搜索行那颗:段里那一行带着三件实的
 * (19 路写死、队排在平台那边、只有支持 automatch 的平台才有这一格),而行尾那颗什么都不带。
 *
 * ✅ **那条诚实债 2026-08-25(S1)已还** —— 不是把链路接上,是**撤回屏上的断言**。
 * `automatch` 是纯前端本地状态;OGS 适配器收 `automatch/start` 后会
 * `_emit("automatch_found", …)`,但 `on_automatch_found` **全仓零订阅者**
 * ⇒ 「适配器 → WS → kiosk 大厅」这一段确实不存在,配上之后盒子不会知道。
 * 接这条链要先定「用户级(非 session 级)平台事件通道落在哪」—— 那是设计决定不是编码,
 * 端到端还要真 OGS 账号 ⇒ 本轮不投(D3)。所以撤掉那枚「排队中」标和那句
 * 「配上就自动进对局」,换成一句**始终成立**的说明。键留着两态:它说的是
 * 「按下去会发生什么」,不是「你现在是什么状态」。
 *
 * ## 「输入之后回车」是**真按回车**,不是边打边搜
 *
 * 旧实现是 400ms 防抖:每敲一个字就向**外部平台**发一次搜索。稿子那行字写的是
 * 「输入之后回车」—— 照它做,顺带把每次击键一个外部请求这件事去掉。
 * 清空再回车 = 回到默认名单。
 */

const PlatformLobbyPage = () => {
  const { t } = useTranslation();
  const { token } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const platform = searchParams.get('platform') || 'ogs';
  const meta = PLATFORM_META[platform] ?? { label: platform, labelCn: platform, color: '#888' };

  const [users, setUsers] = useState<PlatformUser[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [automatch, setAutomatch] = useState(false);
  const [supportsAutomatch, setSupportsAutomatch] = useState(false);
  const [challengeTarget, setChallengeTarget] = useState<PlatformUser | null>(null);
  const [toast, setToast] = useState<{ text: string; bad: boolean } | null>(null);

  useEffect(() => {
    if (!token) return;
    API.platformStatus(token)
      .then((d) => setSupportsAutomatch(
        d.platforms.some((p) => p.platform === platform && p.connected && p.supports_automatch),
      ))
      // 读不到能力就当**没有** —— 摆一颗按不动或按了报错的键,比不摆更糟。
      .catch(() => setSupportsAutomatch(false));
  }, [token, platform]);

  const fetchUsers = useCallback(async (q: string) => {
    if (!token) return;
    setLoaded(false);
    try {
      const data = await API.platformUsers(platform, token, q || undefined);
      setUsers(Array.isArray(data.users) ? data.users : []);
      setFailed(false);
    } catch {
      setUsers([]);
      setFailed(true);
    } finally {
      setLoaded(true);
    }
  }, [token, platform]);

  useEffect(() => { void fetchUsers(query); }, [fetchUsers, query]);

  const sendChallenge = async (user: PlatformUser) => {
    if (!token) return;
    try {
      // 这三项实现里写死,屏上那一行读数说的就是它们 —— 两处必须同源地对得上。
      await API.platformSendChallenge(platform, {
        user_id: user.user_id, board_size: 19, rules: 'chinese', ranked: true,
      }, token);
      setToast({ text: t('platform:challenge_sent', '挑战已发出 —— 接下来在对面那边'), bad: false });
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : t('platform:challenge_failed', '挑战没发出去'), bad: true });
    } finally {
      setChallengeTarget(null);
    }
  };

  const toggleAutomatch = async () => {
    if (!token) return;
    try {
      if (automatch) {
        await API.platformCancelAutomatch(platform, token);
        setAutomatch(false);
      } else {
        await API.platformStartAutomatch(platform, { board_size: 19 }, token);
        setAutomatch(true);
      }
    } catch (e) {
      setToast({ text: e instanceof Error ? e.message : t('platform:automatch_failed', '匹配没开起来'), bad: true });
    }
  };

  const statusOf = (s: string) => (
    s === 'playing' ? t('platform:in_game', '对局中')
      : s === 'seeking' ? t('platform:seeking', '寻找对手中')
        : t('platform:idle', '空闲')
  );

  return (
    <div className="kiosk-layout-b plat-layout" data-testid="platform-lobby-page">
      <KioskPagebar
        backLabel={t('platform:back_to_platforms', '跨平台')}
        onBack={() => navigate('/kiosk/play/cross-platform')}
        title={interpolate(t('platform:lobby_title', '{name} · 大厅'), { name: t(meta.label, meta.labelCn) })}
        sub={t('platform:lobby_sub', '找人挑战，或让平台配一个')}
      />

      <KioskScrollZone>
        {/* 搜索那一行。`.av` 里那个 ⌕ 是**图标位**,不是可点的东西 —— 回车才搜。 */}
        <div className="kiosk-rows">
          <div className="kiosk-row kiosk-row--search">
            <span className="av" aria-hidden="true">⌕</span>
            <div className="kiosk-row__t">
              <b>{t('platform:find_by_name', '按用户名找人')}</b>
              <em>{t('platform:find_hint', '输入之后回车，找不到就是那边没这个人')}</em>
            </div>
            <div className="kiosk-row__end">
              <input
                className="nameinput nameinput--search"
                data-testid="platform-search"
                aria-label={t('platform:find_by_name', '按用户名找人')}
                placeholder={t('local:tap_to_type', '点此输入')}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') setQuery(draft.trim()); }}
              />
            </div>
          </div>
        </div>

        <section className="kiosk-section">
          <KioskSecLabel
            zh={t('platform:results', '搜到的棋手')}
            en="Results"
            // **这句不是旁注**:它是这一屏和屏 06 唯一的语义差别 ——
            // 那边的段位是盒内的,这边是平台那边的,赢了这局盒内段位一动不动。
            value={interpolate(t('platform:rank_is_theirs', '段位是 {name} 那边的'), { name: t(meta.label, meta.labelCn) })}
          />
          <div className="kiosk-rows">
            {failed && (
              <Alert severity="error" sx={{ fontSize: '0.75rem' }}>
                {t('platform:users_failed', '没能从平台取回名单')}
              </Alert>
            )}
            {!failed && !loaded && <p className="lobbyempty">{t('lobby:loading', '正在读…')}</p>}
            {!failed && loaded && users.length === 0 && (
              <p className="lobbyempty">
                {query
                  ? t('platform:no_such_player', '那边没有这个人')
                  : t('platform:search_first', '输入用户名回车找人，或让平台配一个')}
              </p>
            )}
            {loaded && users.map((u) => {
              const playing = u.status === 'playing';
              return (
                <div className="kiosk-row" key={u.user_id} data-testid="platform-user">
                  <span className={`av${playing ? ' dim' : ''}`} aria-hidden="true">
                    {u.username.slice(0, 1)}
                  </span>
                  <div className="kiosk-row__t">
                    <b>{u.username}</b>
                    <em>{t(meta.label, meta.labelCn)} {u.rank} · {statusOf(u.status)}</em>
                  </div>
                  <div className="kiosk-row__end">
                    {/* 对局中的人**收不到挑战** ⇒ 那一行不摆按钮,摆一个状态标。
                        灰掉的按钮会让人一直按。 */}
                    {playing ? (
                      <span className="kiosk-tag">{t('platform:in_game', '对局中')}</span>
                    ) : (
                      <button
                        type="button"
                        className="kiosk-btn kiosk-btn--pill"
                        onClick={() => setChallengeTarget(u)}
                      >{t('platform:challenge', '挑战')}</button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>

        <section className="kiosk-section">
          <KioskSecLabel
            zh={t('platform:challenge_terms', '发起挑战')}
            en="Challenge"
            value={t('platform:terms_fixed', '条件是写死的')}
          />
          <div className="kiosk-rows">
            <div className="kiosk-row">
              <span className="kiosk-row__lead">{t('19x19', '19 路')}</span>
              <div className="kiosk-row__t">
                <b>{t('platform:terms_body', '中国规则 · 计分局')}</b>
                <em>{t('platform:terms_hint', '这三条界面上不选，发出去就是这个条件')}</em>
              </div>
              <div className="kiosk-row__end"><span className="kiosk-tag">{t('platform:fixed', '固定')}</span></div>
            </div>
          </div>
        </section>

        {/* 这一段**按能力出现**(`supports_automatch`)。稿子的组标题右端写着「只有 OGS 有
            这一格」—— 那是说给读稿人听的:屏上只会有当前这一家,那句话在这儿是同义反复。 */}
        {supportsAutomatch && (
          <section className="kiosk-section" data-testid="platform-automatch">
            <KioskSecLabel zh={t('platform:automatch', '自动匹配')} en="Automatch" />
            <div className="kiosk-rows">
              <div className="kiosk-row">
                <span className="kiosk-row__lead">{t('19x19', '19 路')}</span>
                <div className="kiosk-row__t">
                  <b>{interpolate(t('platform:automatch_body', '让 {name} 配一个'), { name: t(meta.label, meta.labelCn) })}</b>
                  {/* ⚠️ **不带状态,只说会发生什么**(2026-08-25,S1)。
                      原来这里在排队时写「排队中 · 配上就自动进对局」—— 后半句是**平的假话**:
                      OGS 适配器确实收 `automatch/start` 并 `_emit("automatch_found", …)`,
                      可 `on_automatch_found` 这个注册口**全仓零订阅者**(只有 emit 处和
                      注册 API 两行)⇒ 平台真给你配上局了,这台盒子永远不会知道。
                      前半句「排队中」也没人维护:它是纯前端本地状态,刷一下页面就没了,
                      而 OGS 那边还排着。**两句都撤,换成一句始终成立的。** */}
                  <em>
                    {interpolate(
                      t('platform:automatch_hint', '队排在 {name} 那边。配上之后不会自动回到这台盒子，要去 {name} 上接着下。'),
                      { name: t(meta.label, meta.labelCn) },
                    )}
                  </em>
                </div>
                {/* 「排队中」那枚标撤了 —— 它断言的是一个**没有任何东西在维护**的状态。
                    键本身留着两态:它说的是**按下去会发生什么**(这一下是开还是撤),
                    那是真的;而且不留着就没法撤销已经发出去的排队。
                    这一屏一共只有这一处能开匹配(搜索行行尾那颗次要按钮按裁定删了)——
                    一个状态摆两个地方,必有一个在撒谎。 */}
                <div className="kiosk-row__end">
                  <button
                    type="button"
                    className="kiosk-btn kiosk-btn--pill"
                    data-testid="platform-automatch-action"
                    onClick={() => { void toggleAutomatch(); }}
                  >
                    {automatch ? t('platform:automatch_cancel', '取消匹配') : t('platform:automatch_start', '开始匹配')}
                  </button>
                </div>
              </div>
            </div>
          </section>
        )}
      </KioskScrollZone>

      {/* 挑战前确认一次:发出去就在对方那边了,撤不回来。 */}
      {challengeTarget && (
        <div className="cdlg" data-testid="platform-challenge-confirm">
          <div className="cdlg__box wdlg" role="dialog" aria-modal="true">
            <h3>{interpolate(t('platform:challenge_ask', '向 {name} 发起挑战？'), { name: challengeTarget.username })}</h3>
            <p className="wdlg__lead">
              {interpolate(
                t('platform:challenge_ask_body', '{name} {rank} · 19 路 · 中国规则 · 计分局。'),
                { name: t(meta.label, meta.labelCn), rank: challengeTarget.rank },
              )}
              <b>{t('platform:challenge_ask_tail', '发出去就在对方那边了。')}</b>
            </p>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={() => setChallengeTarget(null)}>
                {t('cancel', '取消')}
              </button>
              <button type="button" className="main" onClick={() => { void sendChallenge(challengeTarget); }}>
                {t('platform:challenge_send', '发出挑战')}
              </button>
            </div>
          </div>
        </div>
      )}

      <Snackbar open={!!toast} autoHideDuration={4000} onClose={() => setToast(null)}>
        <Alert severity={toast?.bad ? 'error' : 'success'} onClose={() => setToast(null)}>
          {toast?.text}
        </Alert>
      </Snackbar>
    </div>
  );
};

export default PlatformLobbyPage;
