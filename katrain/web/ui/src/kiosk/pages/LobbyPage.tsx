import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Alert } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { getAiLadderStatus } from '../../features/aiLadder/api';
import { websocketUrl } from '../../utils/websocketUrl';
import { Icon } from '../shell/icons';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskScrollZone } from '../shell/KioskScrollZone';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import { interpolate } from '../utils/interpolate';

/**
 * 屏 06 在线大厅(`sample-go/shots/06-lobby.png`,L2 两栏,没有棋盘 ⇒ 页控条通栏),
 * 外加三个态:06b 未登录 · 06c 匹配中 · 06d 收到邀请。
 *
 * 稿子 2026-08-23 按 Fan 的裁定**照国际象棋 05L 那一组重做**:上一版是三张统计卡 +
 * 两张模式卡 + 两段列表竖着摞在一栏里,人和局被切成上下两段,而右边 460 那半屏空着。
 * 现在是两栏 —— **左栏是局、右栏是人**,各自独立滚,主行动钉在右栏底。
 *
 * ## 围棋和国象不一样的四处,每一处都是**围棋给不出国象那个数**
 *
 * ① 国象大厅只有一种对局;围棋有**两种**(`start_matchmaking{game_type:"free"|"rated"}`,
 *    `server.py:2325`),而 rated 那条队要先在「升降级对弈」打完 5 局定级赛
 *    (`server.py:2337` 回 `PLACEMENT_REQUIRED`)⇒ 主行动上面一条分段,没定级时排位灰掉,
 *    底下一行说清为什么。灰而不说原因,这套稿子在别处专门骂过。
 * ② 国象对局卡带「等级 + 等级分」;`/api/v1/games/active/multiplayer`
 *    (`endpoints/games.py:11`)对每一局只回 `player_b` / `player_w` **两个名字字符串**
 *    ⇒ 那一格换成**执黑 / 执白**:这个接口唯一多给出来的事实,也正是点进去观战第一眼要认的。
 * ③ 国象棋友行有四态 + 「我的状态」下拉 + 「已关注」+ 四个筛选。围棋这边:`/ws/lobby`
 *    没有 set-status;关注那套接口**是有的**(`/api/v1/users/follow/{username}`,
 *    galaxy 的 `FriendsPanel` 在用)但**盒内一个入口都没有** ⇒ 关注集恒为空,拿它筛
 *    永远筛不出东西。⇒ 都不画,状态只留**算得出的两态**(空闲 / 对局中,
 *    靠比对左栏那份进行中对局的名字)。
 * ④ 国象房间有钟(15+10);围棋匹配出来的局**压根没有钟** ——
 *    `create_multiplayer_session(pb, pw, b_name, w_name)`(`server.py:2360`)不带任何
 *    时钟参数 ⇒ 一个字都不写时限。**不是「不限时」,是没有那个字段。**
 *
 * ## 和稿子的两处不同,都是「稿子画的今天喂不出来」
 *
 * ⚠️ **段位那一列没有实现。** 稿子按「接上之后」画了它,并在自己的注释里写死了契约:
 *    `/api/v1/users/online` 回的是 `User.rank` / `User.elo_points`,而全仓**没有任何
 *    一处写这两个字段** —— `UPDATE users SET` 只出现在 `core/billing.py`(改的是
 *    credits),`models_db.py:75` 的默认值 `"20k"` 从注册那天起没人动过。围棋**有**真段位,
 *    它在 `ai_ladder_ranked` 那张表里(`has_ladder_rank`),缺的只是 `/users/online`
 *    去 join 一下。
 *    今天照画只有两种结果:每个人恒显「20k / 0」,或者按现有那句
 *    `rank==='20k' && !elo → 无段位` 把整列写死成一个词 —— 而**定过级的人会被这一列
 *    说成没定过级**。所以这一列**不上**:接上那个 join 之后补,位置和宽度稿子里定死了
 *    (`.rk`,62px,名字之后第一格)。这是本屏唯一一处「实现比稿子少」的地方。
 * ⚠️ **06d 那行小字改了。** 稿子写「不接受就一直挂着 —— 邀请没有期限」,只说了一半:
 *    `/ws/lobby` 里 `invite` 只是把一条消息转给对方(`server.py:2402`),**没有 TTL、
 *    没有撤回、也没有 decline** ⇒ 屏上这颗「拒绝」今天只能关掉本地这个弹窗,对面收不到
 *    任何东西。那就得说出来,不能让人以为按了「拒绝」对方会知道。
 *
 * 同理**不画倒计时**:国象 05S 的 60 秒条是他们服务端定的期限,围棋没有那个期限 ——
 * 画一条走完归零、而后端在归零时什么都不做的条,是拿动画伪造一个不存在的裁定。
 * 匹配那一屏的条是**不定长**的(等多久取决于队列里有没有第二个人,这个数产不出来),
 * 已等秒数则是真的(前端自己数)。
 *
 * ## 两个自己写出来又量出来的错(留档,因为它们都不会在 jsdom 里响)
 *
 * ① **无限刷新。** `useTranslation()` 的 `t` **每次渲染都是一个新函数**,把它写进
 *    `useCallback` / `useEffect` 的依赖里,依赖每帧都变 ⇒ `/ws/lobby` 那个 effect 每帧重跑:
 *    新开一条 socket、新起一条定时器、立刻再拉一次两个列表 → setState → 再渲染 → 再跑。
 *    表现是四图那一步 `waitForLoadState('networkidle')` **永远等不到**(网络一刻不停)。
 *    ⇒ effect 里一个 `t` 都不留:失败存**布尔**、通知存**事件**,译文在渲染时才求。
 *    顺带修好第二件事:译文一旦存进 state,切语言之后屏上还留着上一种语言那句。
 *
 * ## 顺手修掉的一个 hooks 顺序错
 *
 * 旧版把「没登录就返回一句 Alert」写在**一部分 hooks 中间** —— `/ws/lobby` 那个
 * `useEffect` 排在早退之后。访客那一帧只注册前几个 hook,登录之后同一个组件实例
 * 多注册一个,React 当场抛「Rendered more hooks than during the previous render」。
 * 现在所有 hook 都排在早退之前,访客那一帧走的是同一条 hook 序列。
 */

interface OnlineUser {
  id: number;
  username: string;
}

interface ActiveGame {
  session_id: string;
  player_b: string;
  player_w: string;
  spectator_count: number;
  move_count: number;
}

/**
 * 认不出来的行**整行丢掉**,不凑合渲染。
 *
 * `await res.json()` 回来的是 `unknown`,一句 `as ActiveGame[]` 只是让类型检查闭嘴 ——
 * 少一个 `session_id`,`.slice(0,4)` 当场抛,而这一屏上面没有 error boundary,
 * 整个 app 白屏。2026-08-24 `navigation.integration.test.tsx` 就是这么炸的:
 * 它那个兜底 fetch 对所有 URL 回同一份分类数组,一行都没有 `session_id`。
 * 认不出的行也**没法观战**(点进去没有 session 可进),所以丢掉比凑合画一张卡诚实。
 */
const isActiveGame = (g: unknown): g is ActiveGame => {
  if (!g || typeof g !== 'object') return false;
  const r = g as Partial<ActiveGame>;
  return typeof r.session_id === 'string' && r.session_id.length > 0
    && typeof r.player_b === 'string' && typeof r.player_w === 'string';
};

type MatchMode = 'free' | 'rated';

/** 定级进度。`remaining === null` = 读不到(接口挂了)—— 那就不许说「你还差 N 局」。 */
type Placement =
  | { placed: true }
  | { placed: false; remaining: number | null };

const LobbyPage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { user, token } = useAuth();

  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [activeGames, setActiveGames] = useState<ActiveGame[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  // ⚠️ 存的是**事件**不是那句译文。`useTranslation()` 的 `t` 每次渲染都是新函数,
  // 把它写进 effect 依赖会让这一屏自己转圈(见文件头「一个无限刷新」那一节);
  // 而且译文一旦存进 state,切语言之后屏上还留着上一种语言的那句。
  const [notice, setNotice] = useState<{ kind: 'placement' } | { kind: 'text'; text: string; bad: boolean } | null>(null);
  const [placement, setPlacement] = useState<Placement>({ placed: false, remaining: null });
  const [mode, setMode] = useState<MatchMode>('free');
  const [isMatching, setIsMatching] = useState(false);
  const [queueTime, setQueueTime] = useState(0);
  const [invitation, setInvitation] = useState<{ from_id: number; from_name: string } | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const authHeaders = useMemo(
    () => (token ? { Authorization: `Bearer ${token}` } : undefined),
    [token],
  );

  const fetchLists = useCallback(async () => {
    if (!authHeaders) return;
    try {
      const [usersRes, gamesRes] = await Promise.all([
        fetch('/api/v1/users/online', { headers: authHeaders }),
        fetch('/api/v1/games/active/multiplayer', { headers: authHeaders }),
      ]);
      if (!usersRes.ok) throw new Error(String(usersRes.status));
      const users: unknown = await usersRes.json();
      setOnlineUsers(Array.isArray(users) ? users as OnlineUser[] : []);
      // 对局那一份挂了不该把整屏判死:名单还是真的,只是左栏空着。
      if (gamesRes.ok) {
        const games: unknown = await gamesRes.json();
        setActiveGames(Array.isArray(games) ? games.filter(isActiveGame) : []);
      }
      setFailed(false);
    } catch {
      setFailed(true);
    } finally {
      setLoaded(true);
    }
  }, [authHeaders]);

  useEffect(() => {
    if (!token) return;
    getAiLadderStatus(token)
      .then((s) => {
        const p = s?.placement_state;
        if (p?.phase === 'placed') setPlacement({ placed: true });
        else if (p?.phase === 'placement') {
          setPlacement({ placed: false, remaining: Math.max(0, p.total_games - p.completed_games) });
        } else setPlacement({ placed: false, remaining: null });
      })
      // 读不到就是读不到:退回「没定级」挡住排位(和服务端同一个结论),但**不报一个编出来的局数**。
      .catch(() => setPlacement({ placed: false, remaining: null }));
  }, [token]);

  // 没定级时排位那一段选不了 —— 万一它当时是选中的,得掉回自由,
  // 否则「开始匹配」会带着一个屏上已经灰掉的模式发出去。
  useEffect(() => {
    if (!placement.placed && mode === 'rated') setMode('free');
  }, [placement.placed, mode]);

  useEffect(() => {
    if (!token) return undefined;
    void fetchLists();
    const refresh = setInterval(() => { void fetchLists(); }, 10000);

    // 走共享 helper,不手搓协议串 —— `websocketUrl` 是上游 dc55f32e 那族修复的落点,
    // 全仓扫描闸盯着它(`utils/websocketUrl.test.ts`)。
    const ws = new WebSocket(websocketUrl('/ws/lobby', token));
    wsRef.current = ws;

    ws.onmessage = (event: MessageEvent<string>) => {
      const data = JSON.parse(event.data) as Record<string, string | number>;
      if (data.type === 'match_found') {
        setIsMatching(false);
        navigate(`/kiosk/play/pvp/room/${String(data.session_id)}`);
      } else if (data.type === 'lobby_update') {
        void fetchLists();
      } else if (data.type === 'invitation') {
        setInvitation({ from_id: Number(data.from_id), from_name: String(data.from_name) });
      } else if (data.type === 'info') {
        setNotice({ kind: 'text', text: String(data.message), bad: false });
      } else if (data.type === 'error') {
        // 服务端也会挡排位(`PLACEMENT_REQUIRED`)—— 前端那道只是免得白排一次队。
        setIsMatching(false);
        setNotice(data.code === 'PLACEMENT_REQUIRED'
          ? { kind: 'placement' }
          : { kind: 'text', text: String(data.message), bad: true });
      }
    };

    return () => {
      ws.close();
      clearInterval(refresh);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [token, fetchLists, navigate]);

  /** 正在下棋的人 = 左栏那份对局里出现过的名字。接口只给名字,所以只能按名字比。 */
  const playingNames = useMemo(
    () => new Set(activeGames.flatMap((g) => [g.player_b, g.player_w])),
    [activeGames],
  );

  // 排序:我自己在最前,然后是**邀得动**的人,最后才是对局中的。
  // 名单一长,能点的那几个不该埋在十几行灰按钮下面。
  const roster = useMemo(() => {
    const rank = (u: OnlineUser) => (u.id === user?.id ? 0 : playingNames.has(u.username) ? 2 : 1);
    return [...onlineUsers].sort((a, b) => rank(a) - rank(b));
  }, [onlineUsers, playingNames, user?.id]);

  const send = (payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify(payload));
  };

  const startMatchmaking = () => {
    send({ type: 'start_matchmaking', game_type: mode });
    setIsMatching(true);
    setQueueTime(0);
    timerRef.current = setInterval(() => setQueueTime((n) => n + 1), 1000);
  };

  const stopMatchmaking = () => {
    send({ type: 'stop_matchmaking' });
    setIsMatching(false);
    if (timerRef.current) clearInterval(timerRef.current);
  };

  // ── 06b 未登录 ──────────────────────────────────────────────────────────
  // 所有 hook 都在上面跑完了,这里才早退 —— 见文件头「hooks 顺序」那一节。
  if (!token) {
    return (
      <div className="kiosk-layout-a lobby-layout" data-testid="lobby-guest">
        <KioskPagebar
          backLabel={t('Back to play', '返回对弈')}
          onBack={() => navigate('/kiosk/play')}
          title={t('lobby:hall_title', '在线大厅')}
          sub={t('lobby:need_login', '需要登录')}
        />
        <div className="kiosk-rail gate-rail">
          <section className="rgate">
            <span><Icon name="users" /></span>
            <h2>{t('lobby:gate_title', '登录后进在线大厅')}</h2>
            <p>
              {t('lobby:gate_why', '大厅要把你的名字和在线状态发给别的盒子上的人,所以它按账号走。访客没有账号,也就没有可以给别人看的身份。')}
            </p>
            <div className="fact">
              <span>{t('lobby:gate_fact_k', '登录之后')}</span>
              <b>{t('lobby:gate_fact_v', '别人能在名单里看到你、邀请你')}</b>
              {/* 稿子这一行写的是段位从哪来 —— 而段位那一列这一版没上(见文件头),
                  照抄就会承诺一个屏上根本没有的东西。换成这一屏真做得到的事。 */}
              <small>{t('lobby:gate_fact_note', '名单只列此刻连着的人:你在就有你,退出就没了')}</small>
            </div>
          </section>
          <p className="rrule">
            {t('lobby:gate_rule_a', '登录只管这一条线。')}
            <b>{t('lobby:gate_rule_b', '人机对弈、本地对局、训练营、复盘、棋谱,访客照样能用。')}</b>
          </p>
          <button type="button" className="kiosk-primary-action" onClick={() => navigate('/kiosk/login')}>
            {t('lobby:go_login', '前往登录')}
          </button>
          <button type="button" className="rsecond" onClick={() => navigate('/kiosk/play')}>
            {t('Back to play', '返回对弈')}
          </button>
        </div>
      </div>
    );
  }

  // 读完之前和读完之后是**两句不同的话**,所以是两个 key ——
  // 同一个 key 配两个默认值,会让「翻译表赢」之后两态说同一句。
  const loading = t('lobby:loading', '正在读…');
  const emptyGames = loaded ? t('lobby:no_games_now', '现在没有人在下') : loading;
  const emptyPlayers = loaded ? t('lobby:no_players_now', '这会儿只有你在线') : loading;

  return (
    <div className="kiosk-layout-a lobby-layout" data-testid="lobby-page">
      <KioskPagebar
        backLabel={t('Back to play', '返回对弈')}
        onBack={() => navigate('/kiosk/play')}
        title={t('lobby:hall_title', '在线大厅')}
        sub={t('lobby:hall_sub', '和别的盒子上的人下 · 也可以进去看')}
      />

      {/* ── 左栏:进行中的对局 ── */}
      <div className="lobbycol">
        <KioskScrollZone
          grow
          className="gamelist"
          head={(
            <KioskSecLabel
              zh={t('lobby:active_games', '进行中的对局')}
              en="In play"
              value={interpolate(t('lobby:games_count', '{n} 局'), { n: activeGames.length })}
            />
          )}
        >
          {failed && <Alert severity="error" sx={{ fontSize: '0.75rem' }}>{t('lobby:load_failed', '读不到大厅 —— 网络或服务没通')}</Alert>}
          {!failed && activeGames.length === 0 && <p className="lobbyempty">{emptyGames}</p>}
          {activeGames.map((g) => (
            <button
              key={g.session_id}
              type="button"
              className="gcard"
              data-testid="lobby-game"
              onClick={() => navigate(`/kiosk/play/pvp/room/${g.session_id}`)}
            >
              <span className="gcard__meta">
                <b>{g.session_id.slice(0, 4)}</b>
                {interpolate(t('lobby:move_no', '第 {n} 手'), { n: g.move_count })}
                {/* 观众数只在**真有观众**时出现 —— 恒挂一个 0 是拿一个空位置冒充一条信息。 */}
                {g.spectator_count > 0 && (
                  <i><Icon name="users" />{g.spectator_count}</i>
                )}
              </span>
              <span className="gcard__vs">
                <span className="gcard__p">
                  <span className="gcard__n">{g.player_b}</span>
                  <span className="gside"><span className="disc b" />{t('lobby:plays_black', '执黑')}</span>
                </span>
                <span className="gcard__mid">{t('lobby:vs', '对')}</span>
                <span className="gcard__p is-r">
                  <span className="gcard__n">{g.player_w}</span>
                  <span className="gside">{t('lobby:plays_white', '执白')}<span className="disc w" /></span>
                </span>
              </span>
            </button>
          ))}
        </KioskScrollZone>
      </div>

      {/* ── 右栏:在线棋手 + 匹配 ── */}
      <div className="lobbycol">
        <KioskScrollZone
          grow
          className="lobbylist"
          head={(
            <KioskSecLabel
              zh={t('lobby:players', '在线棋手')}
              en="Players"
              value={interpolate(t('lobby:online_count', '在线 {n} 人'), { n: onlineUsers.length })}
            />
          )}
        >
          {roster.length === 0 && <p className="lobbyempty">{emptyPlayers}</p>}
          {roster.map((u) => {
            const me = u.id === user?.id;
            const playing = playingNames.has(u.username);
            return (
              <div key={u.id} className={`lobbyrow${me ? ' is-me' : ''}`} data-testid="lobby-player">
                <div className="lobbyrow__id"><h4>{u.username}</h4></div>
                <span className={`lvst${playing ? ' is-play' : ''}`}>
                  {playing ? t('lobby:in_game', '对局中') : t('lobby:idle', '空闲')}
                </span>
                {me ? (
                  <span className="lobbyrow__self">{t('lobby:this_is_you', '这是你')}</span>
                ) : (
                  <button
                    type="button"
                    className="lobbyrow__act"
                    disabled={playing}
                    onClick={() => send({ type: 'invite', target_id: u.id })}
                  >
                    {t('lobby:invite', '邀请')}
                  </button>
                )}
              </div>
            );
          })}
        </KioskScrollZone>

        <p className="lobbylist__note">
          <b>{t('lobby:idle', '空闲')}</b>
          {t('lobby:note_a', '的人可以邀请,')}
          <b>{t('lobby:in_game', '对局中')}</b>
          {t('lobby:note_b', '的不行。左边那一列点进去可以观战。')}
        </p>

        <div className="matchpick">
          <span className="kiosk-seg" role="radiogroup" aria-label={t('lobby:match_mode', '匹配哪一种')}>
            {([['free', t('lobby:mode_free', '自由对局')], ['rated', t('lobby:mode_rated', '排位赛')]] as const).map(
              ([v, label]) => (
                <button
                  key={v}
                  type="button"
                  className="kiosk-seg__btn"
                  role="radio"
                  aria-checked={mode === v}
                  aria-pressed={mode === v}
                  disabled={v === 'rated' && !placement.placed}
                  onClick={() => setMode(v)}
                >{label}</button>
              ),
            )}
          </span>
          {/* 灰了就得有人说原因。读不到定级进度时**不报局数** —— 那个数当时并不知道。 */}
          {!placement.placed && (
            <p className="matchpick__why" data-testid="lobby-rated-why">
              {t('lobby:rated_why_a', '排位赛要先在')}
              <b>{t('lobby:ladder_name', '升降级对弈')}</b>
              {placement.remaining === null
                ? t('lobby:rated_why_b_unknown', '打完 5 局定级赛。')
                : interpolate(t('lobby:rated_why_b', '打完 5 局定级赛 —— 你还差 {n} 局。'), { n: placement.remaining })}
            </p>
          )}
        </div>

        <button
          type="button"
          className="kiosk-primary-action"
          data-testid="lobby-start-match"
          onClick={startMatchmaking}
        >
          {t('lobby:start_match', '开始匹配')}
        </button>
      </div>

      {/* ── 06c 匹配中 ── */}
      {isMatching && (
        <div className="cdlg" data-testid="lobby-matching">
          <div className="cdlg__box wdlg" role="dialog" aria-modal="true" aria-label={t('lobby:matching_title', '正在找对手')}>
            <h3>{t('lobby:matching_title', '正在找对手')}</h3>
            <p className="wdlg__lead">
              {t('lobby:matching_lead_a', '服务端把你放进了')}
              <b>{mode === 'rated' ? t('lobby:mode_rated', '排位赛') : t('lobby:mode_free', '自由对局')}</b>
              {t('lobby:matching_lead_b', '的队列,配上就直接开局,不用再确认一次。')}
            </p>
            {/* 不定长:等多久取决于队列里有没有第二个人,这个数产不出来。 */}
            <div className="wbar"><span className="wbar__loop" /></div>
            <div className="wdlg__row">
              <span className="wdlg__num">
                {t('lobby:waited_a', '已等 ')}<b data-testid="lobby-queue-secs">{queueTime}</b>{t('lobby:waited_b', ' 秒')}
              </span>
              {/* 时限一个字都不写:匹配出来的局没有钟(`create_multiplayer_session` 不带时钟参数)。 */}
              <span className="wdlg__tc">
                {mode === 'rated'
                  ? t('lobby:matching_tc_rated', '配上就开局 · 计段位')
                  : t('lobby:matching_tc_free', '配上就开局 · 不计段位')}
              </span>
            </div>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={stopMatchmaking}>
                {t('lobby:cancel_match', '取消匹配')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 06d 收到邀请 ── */}
      {invitation && (
        <div className="cdlg" data-testid="lobby-invitation">
          <div className="cdlg__box wdlg" role="dialog" aria-modal="true">
            <h3>{interpolate(t('lobby:invite_title', '{name}邀你下一局'), { name: invitation.from_name })}</h3>
            {/* 稿子这一句前面还有「业余 3 段 · 」—— `invitation` 里只有 `from_id` /
                `from_name` / `mode`,没有段位。不编。 */}
            <p className="wdlg__lead">
              <b>{t('lobby:invite_lead_a', '接受就直接开局')}</b>
              {t('lobby:invite_lead_b', ',邀请方执黑。')}
            </p>
            <div className="wdlg__row">
              <span className="wdlg__num">{t('lobby:invite_kind', '自由对局 · 不计段位')}</span>
              {/* 稿子写「不接受就一直挂着 —— 邀请没有期限」,只说了一半:后端没有 decline,
                  这颗「拒绝」只关掉本地这个窗。得说出来,不能让人以为对面会知道。 */}
              <span className="wdlg__tc">{t('lobby:invite_no_decline', '拒绝只关掉这个窗 —— 对面收不到回音,邀请也没有期限')}</span>
            </div>
            <div className="cdlg__acts">
              <button type="button" className="ghost" onClick={() => setInvitation(null)}>
                {t('lobby:decline', '拒绝')}
              </button>
              <button
                type="button"
                className="main"
                onClick={() => {
                  send({ type: 'accept_invite', target_id: invitation.from_id });
                  setInvitation(null);
                }}
              >
                {t('lobby:accept_and_play', '接受并开局')}
              </button>
            </div>
          </div>
        </div>
      )}

      {notice && (
        <Alert
          severity={notice.kind === 'placement' || notice.bad ? 'error' : 'info'}
          onClose={() => setNotice(null)}
          sx={{ position: 'absolute', left: 16, right: 16, bottom: 8, zIndex: 20 }}
        >
          {notice.kind === 'placement'
            ? t('lobby:placement_required', '先在「升降级对弈」打完 5 局定级赛，才能进行人人排位。')
            : notice.text}
        </Alert>
      )}
    </div>
  );
};

export default LobbyPage;
