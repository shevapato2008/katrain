import { translateResult } from '../../utils/resultTranslation';
import { platformLabel } from '../utils/nativePresentation';
import { rankLabel } from '../utils/playerRank';
import { interpolate } from '../utils/interpolate';
import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { useNavigate } from 'react-router-dom';
import { API, ApiError, type PlatformInfo, type GolaxyRoom, type GolaxyOnlinePlayer, type GolaxyPlayerGame } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { PLATFORM_MARKS } from '../constants/platformMarks';
import { KioskCard } from '../shell/KioskCard';
import { PhysicalBoardIcon } from '../shell/PhysicalBoardIcon';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import '../../kiosk-shell/golaxy-home.css';
import './platformReviewed.css';

type Connection =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'expired' }
  | { kind: 'disconnected' }
  | { kind: 'connected'; account: PlatformInfo; token: string | null | undefined };

type ProfileStage = 'main' | 'invite' | 'pending' | 'error' | 'kifu';

const playerRecord = (player: GolaxyOnlinePlayer, t: (key: string, fallback?: string) => string) =>
  Number.isSafeInteger(player.wins) && Number.isSafeInteger(player.losses)
    ? interpolate(t('{wins} 胜 · {losses} 负', '{wins} 胜 · {losses} 负'), { wins: player.wins!, losses: player.losses! }) : null;
const invitationPreference = (player: GolaxyOnlinePlayer) => player.invite_able === true ? '允许邀请' : player.invite_able === false ? '拒绝邀请' : null;
const playerStatus = (player: GolaxyOnlinePlayer) => player.status || invitationPreference(player) || '状态未返回';
const statusClass = (status: string) => status === '空闲' || status === '允许邀请' ? '' : status === '拒绝' || status === '拒绝邀请' || status === '状态未返回' ? ' is-muted' : ' is-busy';
const PlayerAvatar = ({ player }: { player: GolaxyOnlinePlayer }) => player.avatar_url
  ? <img className="golaxy-home__avatar" src={player.avatar_url} alt="" />
  : <span className="golaxy-home__avatar">{player.username.slice(-1)}</span>;

// Reusable view for the verified player identity. Invitation writes remain gated.
export function GolaxyPlayerProfile({ player, token, onClose, initialStage = 'main' }: {
  player: GolaxyOnlinePlayer; token: string | null | undefined; onClose: () => void; initialStage?: ProfileStage;
}) {
  const { t } = useTranslation();
  const [stage, setStage] = useState<ProfileStage>(player.is_self ? 'main' : initialStage);
  const [profileSelf, setProfileSelf] = useState<boolean | undefined>(player.is_self);
  const isSelf = player.is_self === true || profileSelf === true;
  const [mode, setMode] = useState<'screen' | 'physical'>('screen');
  const [followed, setFollowed] = useState<boolean | null>(null);
  const [followBusy, setFollowBusy] = useState(false);
  const [followError, setFollowError] = useState(false);
  const [games, setGames] = useState<GolaxyPlayerGame[]>([]);
  const [gamesTotal, setGamesTotal] = useState<number | null>(null);
  const [gamesPage, setGamesPage] = useState(0);
  const [gamesStatus, setGamesStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [gamesRetry, setGamesRetry] = useState(0);
  const closeButton = useRef<HTMLButtonElement>(null);
  const closeAction = useRef(onClose);
  useEffect(() => { closeAction.current = onClose; }, [onClose]);
  // Focus belongs to this modal lifetime, independently of parent list refreshes.
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') closeAction.current(); };
    document.addEventListener('keydown', closeOnEscape);
    return () => { document.removeEventListener('keydown', closeOnEscape); previousFocus?.focus(); };
  }, []);
  useEffect(() => {
    let active = true;
    API.platformPlayerProfile('golaxy', player.user_id, token)
      .then(({ profile }) => { if (active) { setFollowed(profile.followed); setProfileSelf(profile.is_self); } })
      .catch(() => { if (active) setFollowError(true); });
    return () => { active = false; };
  }, [player.user_id, token]);
  const reloadFollow = async () => {
    setFollowBusy(true);
    setFollowError(false);
    try {
      const { profile } = await API.platformPlayerProfile('golaxy', player.user_id, token);
      setFollowed(profile.followed);
    } catch {
      setFollowed(null);
      setFollowError(true);
    } finally {
      setFollowBusy(false);
    }
  };
  useEffect(() => {
    if (stage !== 'kifu') return;
    let active = true;
    setGamesStatus('loading');
    API.platformPlayerGames('golaxy', player.user_id, token, gamesPage)
      .then(({ games: rows, total }) => { if (active) { setGames((current) => gamesPage === 0 ? rows : [...current, ...rows]); setGamesTotal(total); setGamesStatus('ready'); } })
      .catch(() => { if (active) setGamesStatus('error'); });
    return () => { active = false; };
  }, [stage, player.user_id, token, gamesPage, gamesRetry]);
  const changeFollow = async () => {
    if (isSelf || followed === null || followBusy) return;
    setFollowBusy(true); setFollowError(false);
    try {
      const { profile } = await API.platformFollowPlayer('golaxy', player.user_id, !followed, token);
      setFollowed(profile.followed);
    } catch { setFollowed(null); setFollowError(true); }
    finally { setFollowBusy(false); }
  };
  const record = Number.isSafeInteger(player.wins) && Number.isSafeInteger(player.losses)
    ? interpolate(t('{wins} 胜 · {losses} 负', '{wins} 胜 · {losses} 负'), { wins: player.wins!, losses: player.losses! }) : null;
  const canConfigureInvite = !isSelf && player.invite_able === true;
  const title = { main: t("星阵在线棋友", "星阵在线棋友"), invite: t("发送对局邀请", "发送对局邀请"), pending: t("等待对方回应", "等待对方回应"), error: t("邀请未发送", "邀请未发送"), kifu: t("历史棋谱", "历史棋谱") }[stage];
  return <div className="golaxy-home__profile-layer" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="golaxy-home__profile-dialog" role="dialog" aria-modal="true" aria-labelledby="golaxy-profile-title"
      onKeyDown={(event) => {
        if (event.key !== 'Tab') return;
        const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
        const first = buttons[0]; const last = buttons.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }}>
      <div className="golaxy-home__profile-head"><strong id="golaxy-profile-title">{t("棋友资料", "棋友资料")}</strong><small>{title}</small><button ref={closeButton} onClick={onClose} aria-label={t("关闭棋友资料", "关闭棋友资料")}>×</button></div>
      <div className="golaxy-home__profile-body">
        {stage === 'main' ? <>
          <div className="golaxy-home__profile-hero"><PlayerAvatar player={player} /><div><b>{player.username}</b>{player.rank && <span>{rankLabel(player.rank, t)}</span>}</div>{playerStatus(player) && <span className={`golaxy-home__player-state${statusClass(playerStatus(player))}`}>{platformLabel(playerStatus(player), t)}</span>}</div>
          <div className="golaxy-home__profile-facts">
            <div><small>{t("星阵号", "星阵号")}</small><b>{player.user_id}</b></div>
            {record && <div><small>{t("对弈战绩", "对弈战绩")}</small><b>{record}</b></div>}
            {player.invite_able != null && <div><small>{t("邀请偏好", "邀请偏好")}</small><b>{platformLabel(invitationPreference(player), t)}</b></div>}
          </div>
          {followError && <p className="golaxy-home__profile-feedback" role="alert">{t("关注结果尚未确认。", "关注结果尚未确认。")}<button disabled={followBusy} onClick={reloadFollow}>{t("重新读取关注状态", "重新读取关注状态")}</button></p>}
        </> : stage === 'invite' ? <>
          <p className="golaxy-home__profile-subtitle">{t("邀请这位棋友进行星阵人人对弈", "邀请这位棋友进行星阵人人对弈")}</p>
          <div className="golaxy-home__invite-peer"><PlayerAvatar player={player} /><b>{player.username}</b><small>{[player.rank ? rankLabel(player.rank, t) : null, platformLabel(player.status, t)].filter(Boolean).join(' · ')}</small></div>
          <div className="golaxy-home__invite-label">{t("本机落子方式", "本机落子方式")}</div><div className="golaxy-home__invite-modes"><button aria-pressed={mode === 'screen'} onClick={() => setMode('screen')}>{t("屏幕落子", "屏幕落子")}</button><button aria-pressed={mode === 'physical'} onClick={() => setMode('physical')}><PhysicalBoardIcon />{t("实体盘", "实体盘")}</button></div>
          <p className="golaxy-home__invite-note">{t("邀请对局暂不可用。星阵邀请、取消和进入可落子的对局尚未完成验证。", "邀请对局暂不可用。星阵邀请、取消和进入可落子的对局尚未完成验证。")}</p>
        </> : stage === 'kifu' ? <>
          <p className="golaxy-home__profile-subtitle">{player.username}{t("的星阵人人对弈棋谱", "的星阵人人对弈棋谱")}</p>
          {gamesStatus === 'loading' ? <p role="status">{t("正在读取棋谱…", "正在读取棋谱…")}</p>
            : gamesStatus === 'error' ? <div role="alert">{t("棋谱暂时无法读取。", "棋谱暂时无法读取。")}<button onClick={() => setGamesRetry((value) => value + 1)}>{t("重试", "重试")}</button></div>
              : games.length === 0 ? <p>{t("暂无人人对弈棋谱", "暂无人人对弈棋谱")}</p>
                : <><div className="golaxy-home__kifu-list">{games.map((game) => <div className="golaxy-home__kifu-item" key={game.game_id}>
                  <b>{game.black || t("黑方", "黑方")} · {game.white || t("白方", "白方")}</b>
                  <small>{[game.board_size ? interpolate(t("{board_size} 路", "{board_size} 路"), { board_size: game.board_size }) : null, game.move_number != null ? interpolate(t("{move_number} 手", "{move_number} 手"), { move_number: game.move_number }) : null, game.result ? translateResult(game.result, t) : null].filter(Boolean).join(' · ')}</small>
                </div>)}</div>{gamesTotal !== null && games.length < gamesTotal && <button className="golaxy-home__kifu-more" onClick={() => setGamesPage((value) => value + 1)}>{t("加载更多", "加载更多")}</button>}</>}
        </> : <div className="golaxy-home__invite-pending" role={stage === 'error' ? 'alert' : 'status'}>
          <span className="golaxy-home__invite-ring">{stage === 'pending' ? '⋯' : '!'}</span>
          <strong>{stage === 'pending' ? interpolate(t("邀请已发送 · 等待{username}回应", "邀请已发送 · 等待{username}回应"), { username: player.username }) : t("没能发送对局邀请", "没能发送对局邀请")}</strong>
          <p>{stage === 'pending' ? t("等待星阵确认结果。接受、拒绝、超时或取消后显示明确结果。", "等待星阵确认结果。接受、拒绝、超时或取消后显示明确结果。") : t("对方状态可能已改变，请返回资料后重试。", "对方状态可能已改变，请返回资料后重试。")}</p>
        </div>}
      </div>
      <div className="golaxy-home__profile-foot">
        {stage === 'main' ? <>{!isSelf && <button className="primary" disabled={!canConfigureInvite} onClick={() => setStage('invite')}>{t("邀请对局", "邀请对局")}</button>}<button onClick={() => { setGamesPage(0); setGames([]); setStage('kifu'); }}>{t("查看棋谱", "查看棋谱")}</button>{!isSelf && <button disabled={followed === null || followBusy} onClick={changeFollow}>{followBusy ? t("正在更新", "正在更新") : followed ? t("取消关注", "取消关注") : t("添加关注", "添加关注")}</button>}</>
          : stage === 'invite' ? <><button onClick={() => setStage('main')}>{t("返回资料", "返回资料")}</button><button className="primary" disabled title={t("邀请对局暂不可用", "邀请对局暂不可用")}>{t("发送邀请", "发送邀请")}</button></>
            : stage === 'pending' ? <button disabled title={t("取消邀请尚未接通", "取消邀请尚未接通")}>{t("取消邀请", "取消邀请")}</button> : <button onClick={() => setStage('main')}>{t("返回资料", "返回资料")}</button>}
      </div>
    </section>
  </div>;
}

type LobbyList<T> = { status: 'loading' | 'ready' | 'error'; items: T[]; more: 'idle' | 'loading' | 'error' | 'done'; refreshing: boolean };
type LoadList<T> = (token: string | null | undefined, page: number) => Promise<T[]>;
type UserFilter = 'all' | 'same_level' | 'following';
const loadRooms: LoadList<GolaxyRoom> = (token, page) => API.platformRooms('golaxy', token, page).then(({ rooms }) => rooms);

function useLobbyList<T extends { room_id?: string; user_id?: string }>(
  connected: boolean,
  token: string | null | undefined,
  retry: number,
  load: LoadList<T>,
  setConnection: Dispatch<SetStateAction<Connection>>,
  pageSize?: number,
): LobbyList<T> & { loadMore: (retry?: boolean) => void } {
  const [list, setList] = useState<LobbyList<T>>({ status: 'loading', items: [], more: 'idle', refreshing: false });
  const moreAction = useRef<(retry?: boolean) => void>(() => {});

  useEffect(() => {
    setList({ status: 'loading', items: [], more: 'idle', refreshing: false });
    moreAction.current = () => {};
    if (!connected) return;
    let active = true;
    let latestRequest = 0;
    let busy = false;
    let moreError = false;
    let pages: T[][] = [];
    let timer: number | undefined;
    const items = () => [...new Map(pages.flat().map((item) => [item.room_id ?? item.user_id, item])).values()];
    const hasMore = () => pages.length > 0 && pages.at(-1)!.length > 0
      && (pageSize === undefined || pages.at(-1)!.length >= pageSize);
    const schedule = () => {
      window.clearTimeout(timer);
      if (active && !document.hidden) timer = window.setTimeout(refresh, 30_000);
    };
    const fail = (error: unknown, append: boolean) => {
      if (error instanceof ApiError && error.status === 401) {
        active = false;
        setConnection((current) => current.kind === 'connected' ? { kind: 'expired' } : current);
      } else if (append) {
        moreError = true;
        setList((current) => ({ ...current, more: 'error', refreshing: false }));
      } else {
        setList({ status: 'error', items: [], more: 'idle', refreshing: false });
      }
    };
    async function refresh() {
      if (!active || document.hidden || busy) return;
      busy = true;
      const request = ++latestRequest;
      if (pages.length) setList((current) => ({ ...current, refreshing: true }));
      try {
        const refreshed: T[][] = [];
        for (let page = 0; page < Math.max(1, pages.length); page++) {
          const rows = await load(token, page);
          if (!active || request !== latestRequest) return;
          refreshed.push(rows);
          if (rows.length === 0) break;
        }
        pages = refreshed;
        moreError = false;
        setList({ status: 'ready', items: items(), more: hasMore() ? 'idle' : 'done', refreshing: false });
      } catch (error) {
        if (active && request === latestRequest) fail(error, false);
      } finally {
        if (active && request === latestRequest) { busy = false; schedule(); }
      }
    }
    moreAction.current = async (retryMore = false) => {
      if (!active || document.hidden || busy || !hasMore() || (moreError && !retryMore)) return;
      busy = true;
      const request = ++latestRequest;
      setList((current) => ({ ...current, more: 'loading' }));
      try {
        const rows = await load(token, pages.length);
        if (!active || request !== latestRequest) return;
        pages = [...pages, rows];
        moreError = false;
        setList({ status: 'ready', items: items(), more: hasMore() ? 'idle' : 'done', refreshing: false });
      } catch (error) {
        if (active && request === latestRequest) fail(error, true);
      } finally {
        if (active && request === latestRequest) { busy = false; schedule(); }
      }
    };
    const onVisibilityChange = () => {
      window.clearTimeout(timer);
      latestRequest += 1;
      busy = false;
      if (!document.hidden) void refresh();
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    void refresh();
    return () => {
      active = false;
      latestRequest += 1;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [connected, token, retry, load, setConnection, pageSize]);

  return { ...list, loadMore: (retryMore) => moreAction.current(retryMore) };
}

const GolaxyHomePage = ({ profileInitialStage = 'main' }: { profileInitialStage?: ProfileStage }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [connection, setConnection] = useState<Connection>({ kind: 'loading' });
  const [retry, setRetry] = useState(0);
  const [accountMenu, setAccountMenu] = useState(false);
  const [accountIntent, setAccountIntent] = useState<'switch' | 'logout' | null>(null);
  const [accountBusy, setAccountBusy] = useState(false);
  const [accountError, setAccountError] = useState(false);
  const accountGeneration = useRef(0);
  const [selectedPlayer, setSelectedPlayer] = useState<GolaxyOnlinePlayer | null>(null);
  const [tab, setTab] = useState<'rooms' | 'users'>('rooms');
  const [userFilter, setUserFilter] = useState<UserFilter>('all');
  const loadUsers = useCallback<LoadList<GolaxyOnlinePlayer>>((authToken, page) => API.platformUsers<GolaxyOnlinePlayer>('golaxy', authToken, undefined, { page, filter: userFilter }).then(({ users }) => users), [userFilter]);
  const listBody = useRef<HTMLDivElement>(null);
  const [listRetries, setListRetries] = useState({ rooms: 0, users: 0 });
  const currentConnection: Connection = connection.kind === 'connected' && connection.token !== token
    ? { kind: 'loading' }
    : connection;
  const connected = currentConnection.kind === 'connected';
  const roomsList = useLobbyList(connected, token, listRetries.rooms, loadRooms, setConnection);
  const usersList = useLobbyList(connected, token, listRetries.users, loadUsers, setConnection, userFilter === 'following' ? 20 : undefined);
  const rooms = roomsList.items;
  const users = usersList.items;
  const lists = { rooms: roomsList.status, users: usersList.status };
  const activeList = tab === 'rooms' ? roomsList : usersList;
  useEffect(() => { if (listBody.current) listBody.current.scrollTop = 0; }, [tab, userFilter]);
  const profilePlayer = selectedPlayer ? users.find((user) => user.user_id === selectedPlayer.user_id) ?? selectedPlayer : null;

  useEffect(() => {
    setSelectedPlayer(null); setAccountMenu(false); setAccountIntent(null); setAccountBusy(false); setAccountError(false);
  }, [token, connected]);
  useEffect(() => {
    const generation = ++accountGeneration.current;
    return () => { if (accountGeneration.current === generation) accountGeneration.current++; };
  }, [token]);

  const disconnectAccount = async () => {
    if (!accountIntent || accountBusy) return;
    const generation = accountGeneration.current;
    const intent = accountIntent;
    setAccountBusy(true);
    setAccountError(false);
    try {
      await API.platformLogout('golaxy', token);
      if (accountGeneration.current !== generation) return;
      setConnection({ kind: 'disconnected' });
      setAccountMenu(false);
      if (intent === 'switch') navigate('/kiosk/play/cross-platform/login/golaxy');
    } catch {
      if (accountGeneration.current !== generation) return;
      setAccountBusy(false);
      setAccountError(true);
    }
  };

  const selectTab = (next: 'rooms' | 'users') => {
    setTab(next);
  };

  useEffect(() => {
    let cancelled = false;
    if (!isAuthenticated) {
      setConnection({ kind: 'disconnected' });
      return;
    }
    setConnection({ kind: 'loading' });
    API.platformStatus(token)
      .then(({ platforms }) => {
        if (cancelled) return;
        const account = platforms.find((entry) => entry.platform === 'golaxy');
        setConnection(account?.connected ? { kind: 'connected', account, token } : { kind: 'disconnected' });
      })
      .catch(() => { if (!cancelled) setConnection({ kind: 'error' }); });
    return () => { cancelled = true; };
  }, [isAuthenticated, token, retry]);

  return (
    <div className="kiosk-layout-b golaxy-home" data-testid="golaxy-home-page">
      <div className="golaxy-home__pagebar"><KioskPagebar
        backLabel={t('platform:back_to_play', '返回对弈')}
        onBack={() => navigate('/kiosk/play')}
        title={<span className="golaxy-home__title">
          <img src={PLATFORM_MARKS.golaxy.src} alt="" />
          <strong>{t('platform:golaxy', '星阵围棋')}</strong>
        </span>}
        status={connected ? t('platform:connected', '已连接') : undefined}
      />
      {connected && <button className="golaxy-home__account-trigger" aria-haspopup="true" aria-expanded={accountMenu} disabled={accountBusy} onClick={() => { setAccountMenu(!accountMenu); setAccountIntent(null); setAccountError(false); }}><span>{t("当前账号", "当前账号")}</span><b>{currentConnection.kind === 'connected' && (currentConnection.account.saved_username?.trim() || t("昵称未获取", "昵称未获取"))}</b><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3 6 5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" /></svg></button>}
      </div>
      {accountMenu && connected && <div className="golaxy-home__account-menu"><h3>{t("星阵账号 ·", "星阵账号 ·")} {currentConnection.kind === 'connected' && (currentConnection.account.saved_username?.trim() || t("昵称未获取", "昵称未获取"))}</h3><p>{t("当前账号已连接。切换账号会先断开当前星阵连接，再进入星阵登录页。", "当前账号已连接。切换账号会先断开当前星阵连接，再进入星阵登录页。")}</p><div><button disabled={accountBusy} onClick={() => { setAccountIntent('switch'); setAccountError(false); }}>{t("切换账号", "切换账号")}</button><button disabled={accountBusy} onClick={() => { setAccountIntent('logout'); setAccountError(false); }}>{t("退出星阵", "退出星阵")}</button></div>{accountIntent && <div className="golaxy-home__account-confirm"><p>{t("确认", "确认")}{accountIntent === 'switch' ? t("断开当前账号并切换", "断开当前账号并切换") : t("退出当前星阵账号", "退出当前星阵账号")}？</p>{accountError && <p role="alert">{t("没能断开星阵账号，请重试。", "没能断开星阵账号，请重试。")}</p>}<button disabled={accountBusy} onClick={disconnectAccount}>{accountError ? t("重试断开", "重试断开") : accountBusy ? t("正在断开", "正在断开") : t("确认", "确认")}</button><button disabled={accountBusy} onClick={() => setAccountIntent(null)}>{t("取消", "取消")}</button></div>}</div>}

      <div className="golaxy-home__scroll">
        {currentConnection.kind === 'loading' && <div className="golaxy-home__state" role="status">{t('platform:loading_connection', '正在读取星阵连接')}</div>}
        {currentConnection.kind === 'error' && (
          <div className="golaxy-home__state" role="alert">
            <p>{t('platform:connection_check_failed', '没能读取星阵连接状态')}</p>
            <button type="button" onClick={() => setRetry((count) => count + 1)}>{t('common:retry', '重试')}</button>
          </div>
        )}
        {currentConnection.kind === 'disconnected' && (
          <div className="golaxy-home__state">
            <p>{t('platform:not_connected', '星阵账号未连接')}</p>
            <button type="button" onClick={() => navigate('/kiosk/play/cross-platform/login/golaxy')}>{t('platform:connect_golaxy', '连接星阵')}</button>
          </div>
        )}
        {currentConnection.kind === 'expired' && (
          <div className="golaxy-home__state" role="alert">
            <p>{t('platform:golaxy_login_expired', '星阵登录已失效')}</p>
            <button type="button" onClick={() => navigate('/kiosk/play/cross-platform/login/golaxy')}>{t('platform:golaxy_reconnect', '星阵登录已失效，重新连接')}</button>
          </div>
        )}
        {connected && (
          <>
            <section className="golaxy-home__section">
              <KioskSecLabel zh={t('platform:start_game', '开一局')} en="Start" />
              <div className="kiosk-cards golaxy-home__cards">
                <KioskCard title={t('platform:quick_match', '快速匹配')} sub={t('platform:quick_setup', '按星阵规则匹配棋友')} icon="users" onClick={() => navigate('/kiosk/play/cross-platform/golaxy/setup/quick')} />
                <KioskCard title={t('platform:rooms', '房间')} sub={t('platform:room_setup', '创建或按房号加入')} icon="grid-nine" onClick={() => navigate('/kiosk/play/cross-platform/golaxy/setup/room')} />
                <KioskCard title={t('platform:engine_play', '人机对弈')} sub={t('platform:engine_setup', '星阵 AI · 选档开局')} icon="robot" onClick={() => navigate('/kiosk/play/cross-platform/engine/golaxy')} />
              </div>
            </section>

            <section className="golaxy-home__section">
              <KioskSecLabel zh={t('platform:lobby', '对战大厅')} en="Lobby" />
              <div className="golaxy-home__lobby">
              <div className="golaxy-home__list-head">
                <div className="golaxy-home__tabs" role="tablist" aria-label={t('platform:lobby', '星阵大厅')}>
                  <button role="tab" aria-selected={tab === 'rooms'} onClick={() => selectTab('rooms')}>{t('platform:all_games', '全部对局')}</button>
                  <button role="tab" aria-selected={tab === 'users'} onClick={() => selectTab('users')}>{t('platform:online_players', '在线棋友')}</button>
                </div>
                <span>{tab === 'rooms' ? t("点选一局进入只读观战 · 按星阵状态更新", "点选一局进入只读观战 · 按星阵状态更新") : t("级别、胜负和状态以星阵返回为准", "级别、胜负和状态以星阵返回为准")}</span>
              </div>
              <div className="golaxy-home__list-body" ref={listBody} onScroll={(event) => {
                const { scrollHeight, scrollTop, clientHeight } = event.currentTarget;
                if (scrollHeight - scrollTop - clientHeight <= 64 && activeList.status === 'ready') activeList.loadMore();
              }}>
              {lists[tab] === 'loading' && <p role="status" className="golaxy-home__empty">{tab === 'rooms' ? t('platform:loading_rooms', '正在读取星阵对局') : t('platform:loading_users', '正在读取在线棋友')}</p>}
              {lists[tab] === 'error' && <div className="golaxy-home__state" role="alert"><p>{tab === 'rooms' ? t('platform:rooms_failed', '没能读取星阵对局') : t('platform:users_failed', '没能读取在线棋友')}</p><button onClick={() => setListRetries((counts) => ({ ...counts, [tab]: counts[tab] + 1 }))}>{t('common:retry', '重试')}</button></div>}
              {lists[tab] === 'ready' && (tab === 'rooms' ? rooms.length === 0 : users.length === 0) && <p className="golaxy-home__empty">{tab === 'rooms' ? t('platform:no_rooms', '暂无对局') : t('platform:no_users', '暂无在线棋友')}</p>}
              {tab === 'users' && <div className="golaxy-home__player-filters"><button aria-pressed={userFilter === 'all'} onClick={() => setUserFilter('all')}>{t("全部棋友", "全部棋友")}</button><button aria-pressed={userFilter === 'same_level'} onClick={() => setUserFilter('same_level')}>{t("同级别", "同级别")}</button><button aria-pressed={userFilter === 'following'} onClick={() => setUserFilter('following')}>{t("我的关注", "我的关注")}</button><small>{t("胜负与状态以星阵为准", "胜负与状态以星阵为准")}</small></div>}
              {lists[tab] === 'ready' && <div className="golaxy-home__room-grid" role="tabpanel">
                {tab === 'rooms' ? rooms.map((room) => <button key={room.room_id} className="golaxy-home__room" onClick={() => navigate(`/kiosk/play/cross-platform/golaxy/spectate/${encodeURIComponent(room.room_id)}`)}>
                  <span className="golaxy-home__room-top"><b>{room.room_number ? interpolate(t("{room_number} {value2}", "{room_number} {value2}"), { room_number: room.room_number, value2: t('platform:room_suffix', '房') }) : t('platform:room', '房间')}</b>{room.room_type && <span>{platformLabel(room.room_type, t)}</span>}{room.handicap !== null && <span>{room.handicap === 0 ? t('platform:even_game', '分先') : room.handicap === -1 ? t('platform:black_first', '让先') : interpolate(t("{value1} {handicap} {value3}", "{value1} {handicap} {value3}"), { value1: t('platform:handicap', '让'), handicap: room.handicap, value3: t('platform:stones', '子') })}</span>}{room.room_user_count != null && <small>{room.room_user_count} {t("人在房间", "人在房间")}</small>}</span>
                  <span className="golaxy-home__room-body">
                    <span className="golaxy-home__seat"><span className="golaxy-home__avatar">{room.black?.username.slice(-1) || '—'}</span><span><b>{room.black?.username || t('platform:unknown_player', '棋手信息待返回')}</b>{room.black?.rank && <small>{rankLabel(room.black.rank, t)}</small>}</span></span>
                    <span className="golaxy-home__phase"><span aria-hidden="true" className="golaxy-home__mini-board" />{room.move_number != null ? interpolate(t("{move_number} 手", "{move_number} 手"), { move_number: room.move_number }) : platformLabel(room.phase, t)}</span>
                    <span className="golaxy-home__seat golaxy-home__seat--white"><span className="golaxy-home__avatar">{room.white?.username.slice(-1) || '—'}</span><span><b>{room.white?.username || t('platform:unknown_player', '棋手信息待返回')}</b>{room.white?.rank && <small>{rankLabel(room.white.rank, t)}</small>}</span></span>
                  </span>
                </button>) : users.map((user) => <button key={user.user_id} className="golaxy-home__player" onClick={() => setSelectedPlayer(user)} aria-label={interpolate(t("查看{username}的个人资料", "查看{username}的个人资料"), { username: user.username })}><PlayerAvatar player={user} /><span className="golaxy-home__player-name"><b>{user.username}</b>{user.rank && <small>{rankLabel(user.rank, t)}</small>}</span>{playerRecord(user, t) && <span className="golaxy-home__record">{playerRecord(user, t)}</span>}{playerStatus(user) && <span className={`golaxy-home__player-state${statusClass(playerStatus(user))}`}>{platformLabel(playerStatus(user), t)}</span>}</button>)}
              </div>}
              {lists[tab] === 'ready' && <div className="golaxy-home__empty">
                {activeList.refreshing ? <p role="status">{t("正在更新列表…", "正在更新列表…")}</p> : activeList.more === 'loading' ? <p role="status">{t("正在加载更多…", "正在加载更多…")}</p>
                  : activeList.more === 'error' ? <div role="alert"><p>{t("没能读取更多，请重试", "没能读取更多，请重试")}</p><button onClick={() => activeList.loadMore(true)}>{t("重试加载更多", "重试加载更多")}</button></div>
                    : activeList.more === 'done' && activeList.items.length > 0 ? <p>{t("没有更多了", "没有更多了")}</p>
                      : activeList.items.length > 0 && <button onClick={() => activeList.loadMore()}>{tab === 'rooms' ? t("加载更多对局", "加载更多对局") : t("加载更多棋友", "加载更多棋友")}</button>}
              </div>}
              </div>
              </div>
            </section>
          </>
        )}
      </div>
      {profilePlayer && connected && <GolaxyPlayerProfile key={profilePlayer.user_id} player={profilePlayer} token={token} initialStage={profileInitialStage} onClose={() => setSelectedPlayer(null)} />}
    </div>
  );
};

export default GolaxyHomePage;
