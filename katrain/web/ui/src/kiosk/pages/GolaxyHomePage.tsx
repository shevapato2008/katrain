import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from 'react';
import { useNavigate } from 'react-router-dom';
import { API, ApiError, type PlatformInfo, type GolaxyRoom, type GolaxyOnlinePlayer } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { PLATFORM_MARKS } from '../constants/platformMarks';
import { KioskCard } from '../shell/KioskCard';
import { KioskPagebar } from '../shell/KioskPagebar';
import { KioskSecLabel } from '../shell/KioskSecLabel';
import '../../kiosk-shell/golaxy-home.css';

type Connection =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'expired' }
  | { kind: 'disconnected' }
  | { kind: 'connected'; account: PlatformInfo; token: string | null | undefined };

type ProfileStage = 'main' | 'invite' | 'pending' | 'error';

const playerRecord = (player: GolaxyOnlinePlayer) =>
  Number.isSafeInteger(player.wins) && Number.isSafeInteger(player.losses)
    ? `${player.wins} 胜 · ${player.losses} 负` : null;
const invitationPreference = (player: GolaxyOnlinePlayer) => player.invite_able === true ? '允许邀请' : player.invite_able === false ? '拒绝邀请' : null;
const playerStatus = (player: GolaxyOnlinePlayer) => player.status || invitationPreference(player) || '状态未返回';
const statusClass = (status: string) => status === '空闲' || status === '允许邀请' ? '' : status === '拒绝' || status === '拒绝邀请' || status === '状态未返回' ? ' is-muted' : ' is-busy';
const PlayerAvatar = ({ player }: { player: GolaxyOnlinePlayer }) => player.avatar_url
  ? <img className="golaxy-home__avatar" src={player.avatar_url} alt="" />
  : <span className="golaxy-home__avatar">{player.username.slice(-1)}</span>;

// Reusable view for the verified player identity. No invitation write is wired yet.
export function GolaxyPlayerProfile({ player, onClose, initialStage = 'main' }: {
  player: GolaxyOnlinePlayer; onClose: () => void; initialStage?: ProfileStage;
}) {
  const [stage, setStage] = useState<ProfileStage>(initialStage);
  const [mode, setMode] = useState<'screen' | 'physical'>('screen');
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
  const record = playerRecord(player);
  const canConfigureInvite = player.invite_able === true;
  const title = { main: '星阵在线棋友', invite: '发送对局邀请', pending: '等待对方回应', error: '邀请未发送' }[stage];
  return <div className="golaxy-home__profile-layer" onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="golaxy-home__profile-dialog" role="dialog" aria-modal="true" aria-labelledby="golaxy-profile-title"
      onKeyDown={(event) => {
        if (event.key !== 'Tab') return;
        const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
        const first = buttons[0]; const last = buttons.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }}>
      <div className="golaxy-home__profile-head"><strong id="golaxy-profile-title">棋友资料</strong><small>{title}</small><button ref={closeButton} onClick={onClose} aria-label="关闭棋友资料">×</button></div>
      <div className="golaxy-home__profile-body">
        {stage === 'main' ? <>
          <div className="golaxy-home__profile-hero"><PlayerAvatar player={player} /><div><b>{player.username}</b>{player.rank && <span>{player.rank}</span>}</div>{playerStatus(player) && <span className={`golaxy-home__player-state${statusClass(playerStatus(player))}`}>{playerStatus(player)}</span>}</div>
          <div className="golaxy-home__profile-facts">
            <div><small>星阵号</small><b>{player.user_id}</b></div>
            {record && <div><small>对弈战绩</small><b>{record}</b></div>}
            {player.invite_able != null && <div><small>邀请偏好</small><b>{invitationPreference(player)}</b></div>}
          </div>
        </> : stage === 'invite' ? <>
          <p className="golaxy-home__profile-subtitle">邀请这位棋友进行星阵人人对弈</p>
          <div className="golaxy-home__invite-peer"><PlayerAvatar player={player} /><b>{player.username}</b><small>{[player.rank, player.status].filter(Boolean).join(' · ')}</small></div>
          <div className="golaxy-home__invite-label">本机落子方式</div><div className="golaxy-home__invite-modes"><button aria-pressed={mode === 'screen'} onClick={() => setMode('screen')}>屏幕落子</button><button aria-pressed={mode === 'physical'} onClick={() => setMode('physical')}>实体棋盘</button></div>
          <p className="golaxy-home__invite-note">邀请对局暂不可用。星阵邀请、取消和进入可落子的对局尚未完成验证。</p>
        </> : <div className="golaxy-home__invite-pending" role={stage === 'error' ? 'alert' : 'status'}>
          <span className="golaxy-home__invite-ring">{stage === 'pending' ? '⋯' : '!'}</span>
          <strong>{stage === 'pending' ? `邀请已发送 · 等待${player.username}回应` : '没能发送对局邀请'}</strong>
          <p>{stage === 'pending' ? '等待星阵确认结果。接受、拒绝、超时或取消后显示明确结果。' : '对方状态可能已改变，请返回资料后重试。'}</p>
        </div>}
      </div>
      <div className="golaxy-home__profile-foot">
        {stage === 'main' ? <><button className="primary" disabled={!canConfigureInvite} onClick={() => setStage('invite')}>邀请对局</button><button disabled title="棋谱接口尚未接通">查看棋谱</button><button disabled title="关注接口尚未接通">添加关注</button></>
          : stage === 'invite' ? <><button onClick={() => setStage('main')}>返回资料</button><button className="primary" disabled title="邀请对局暂不可用">发送邀请</button></>
            : stage === 'pending' ? <button disabled title="取消邀请尚未接通">取消邀请</button> : <button onClick={() => setStage('main')}>返回资料</button>}
      </div>
    </section>
  </div>;
}

type LobbyList<T> = { status: 'loading' | 'ready' | 'error'; items: T[] };
type LoadList<T> = (token: string | null | undefined) => Promise<T[]>;

const loadRooms: LoadList<GolaxyRoom> = (token) => API.platformRooms('golaxy', token).then(({ rooms }) => rooms);
const loadUsers: LoadList<GolaxyOnlinePlayer> = (token) => API.platformUsers<GolaxyOnlinePlayer>('golaxy', token).then(({ users }) => users);

function useLobbyList<T>(
  connected: boolean,
  token: string | null | undefined,
  retry: number,
  load: LoadList<T>,
  setConnection: Dispatch<SetStateAction<Connection>>,
): LobbyList<T> {
  const [list, setList] = useState<LobbyList<T>>({ status: 'loading', items: [] });

  useEffect(() => {
    if (!connected) {
      setList({ status: 'loading', items: [] });
      return;
    }
    let active = true;
    let latestRequest = 0;
    let timer: number | undefined;
    const refresh = () => {
      if (!active || document.hidden) return;
      const request = ++latestRequest;
      load(token).then((items) => {
        if (active && request === latestRequest) setList({ status: 'ready', items });
      }).catch((error: unknown) => {
        if (!active || request !== latestRequest) return;
        if (error instanceof ApiError && error.status === 401) {
          active = false;
          setConnection((current) => current.kind === 'connected' ? { kind: 'expired' } : current);
        } else {
          setList({ status: 'error', items: [] });
        }
      }).finally(() => {
        if (active && request === latestRequest && !document.hidden) timer = window.setTimeout(refresh, 30_000);
      });
    };
    const onVisibilityChange = () => {
      window.clearTimeout(timer);
      latestRequest += 1;
      if (!document.hidden) refresh();
    };

    setList({ status: 'loading', items: [] });
    document.addEventListener('visibilitychange', onVisibilityChange);
    refresh();
    return () => {
      active = false;
      latestRequest += 1;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    };
  }, [connected, token, retry, load, setConnection]);

  return list;
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
  const [listRetries, setListRetries] = useState({ rooms: 0, users: 0 });
  const currentConnection: Connection = connection.kind === 'connected' && connection.token !== token
    ? { kind: 'loading' }
    : connection;
  const connected = currentConnection.kind === 'connected';
  const roomsList = useLobbyList(connected, token, listRetries.rooms, loadRooms, setConnection);
  const usersList = useLobbyList(connected, token, listRetries.users, loadUsers, setConnection);
  const rooms = roomsList.items;
  const users = usersList.items;
  const lists = { rooms: roomsList.status, users: usersList.status };
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
      {connected && <button className="golaxy-home__account-trigger" aria-haspopup="true" aria-expanded={accountMenu} disabled={accountBusy} onClick={() => { setAccountMenu(!accountMenu); setAccountIntent(null); setAccountError(false); }}><span>当前账号</span><b>{currentConnection.kind === 'connected' && (currentConnection.account.saved_username?.trim() || '昵称未获取')}</b><svg viewBox="0 0 16 16" aria-hidden="true"><path d="m3 6 5 5 5-5" fill="none" stroke="currentColor" strokeWidth="2" /></svg></button>}
      </div>
      {accountMenu && connected && <div className="golaxy-home__account-menu"><h3>星阵账号 · {currentConnection.kind === 'connected' && (currentConnection.account.saved_username?.trim() || '昵称未获取')}</h3><p>当前账号已连接。切换账号会先断开当前星阵连接，再进入星阵登录页。</p><div><button disabled={accountBusy} onClick={() => { setAccountIntent('switch'); setAccountError(false); }}>切换账号</button><button disabled={accountBusy} onClick={() => { setAccountIntent('logout'); setAccountError(false); }}>退出星阵</button></div>{accountIntent && <div className="golaxy-home__account-confirm"><p>确认{accountIntent === 'switch' ? '断开当前账号并切换' : '退出当前星阵账号'}？</p>{accountError && <p role="alert">没能断开星阵账号，请重试。</p>}<button disabled={accountBusy} onClick={disconnectAccount}>{accountError ? '重试断开' : accountBusy ? '正在断开' : '确认'}</button><button disabled={accountBusy} onClick={() => setAccountIntent(null)}>取消</button></div>}</div>}

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
                <span>{tab === 'rooms' ? '点选一局进入只读观战 · 按星阵状态更新' : '级别、胜负和状态以星阵返回为准'}</span>
              </div>
              <div className="golaxy-home__list-body">
              {lists[tab] === 'loading' && <p role="status" className="golaxy-home__empty">{tab === 'rooms' ? t('platform:loading_rooms', '正在读取星阵对局') : t('platform:loading_users', '正在读取在线棋友')}</p>}
              {lists[tab] === 'error' && <div className="golaxy-home__state" role="alert"><p>{tab === 'rooms' ? t('platform:rooms_failed', '没能读取星阵对局') : t('platform:users_failed', '没能读取在线棋友')}</p><button onClick={() => setListRetries((counts) => ({ ...counts, [tab]: counts[tab] + 1 }))}>{t('common:retry', '重试')}</button></div>}
              {lists[tab] === 'ready' && (tab === 'rooms' ? rooms.length === 0 : users.length === 0) && <p className="golaxy-home__empty">{tab === 'rooms' ? t('platform:no_rooms', '暂无对局') : t('platform:no_users', '暂无在线棋友')}</p>}
              {tab === 'users' && <div className="golaxy-home__player-filters"><button aria-pressed="true">全部棋友</button><button disabled title="同级筛选尚未接通">同级别</button><button disabled title="关注接口尚未接通">我的关注</button><small>胜负与状态以星阵为准</small></div>}
              {lists[tab] === 'ready' && <div className="golaxy-home__room-grid" role="tabpanel">
                {tab === 'rooms' ? rooms.map((room) => <button key={room.room_id} className="golaxy-home__room" onClick={() => navigate(`/kiosk/play/cross-platform/golaxy/spectate/${encodeURIComponent(room.room_id)}`)}>
                  <span className="golaxy-home__room-top"><b>{room.room_number ? `${room.room_number} ${t('platform:room_suffix', '房')}` : t('platform:room', '房间')}</b>{room.room_type && <span>{room.room_type}</span>}{room.handicap !== null && <span>{room.handicap === 0 ? t('platform:even_game', '分先') : room.handicap === -1 ? t('platform:black_first', '让先') : `${t('platform:handicap', '让')} ${room.handicap} ${t('platform:stones', '子')}`}</span>}{room.room_user_count != null && <small>{room.room_user_count} 人在房间</small>}</span>
                  <span className="golaxy-home__room-body">
                    <span className="golaxy-home__seat"><span className="golaxy-home__avatar">{room.black?.username.slice(-1) || '—'}</span><span><b>{room.black?.username || t('platform:unknown_player', '棋手信息待返回')}</b>{room.black?.rank && <small>{room.black.rank}</small>}</span></span>
                    <span className="golaxy-home__phase"><span aria-hidden="true" className="golaxy-home__mini-board" />{room.move_number != null ? `${room.move_number} 手` : room.phase}</span>
                    <span className="golaxy-home__seat golaxy-home__seat--white"><span className="golaxy-home__avatar">{room.white?.username.slice(-1) || '—'}</span><span><b>{room.white?.username || t('platform:unknown_player', '棋手信息待返回')}</b>{room.white?.rank && <small>{room.white.rank}</small>}</span></span>
                  </span>
                </button>) : users.map((user) => <button key={user.user_id} className="golaxy-home__player" onClick={() => setSelectedPlayer(user)} aria-label={`查看${user.username}的个人资料`}><PlayerAvatar player={user} /><span className="golaxy-home__player-name"><b>{user.username}</b>{user.rank && <small>{user.rank}</small>}</span>{playerRecord(user) && <span className="golaxy-home__record">{playerRecord(user)}</span>}{playerStatus(user) && <span className={`golaxy-home__player-state${statusClass(playerStatus(user))}`}>{playerStatus(user)}</span>}</button>)}
              </div>}
              </div>
              </div>
            </section>
          </>
        )}
      </div>
      {profilePlayer && connected && <GolaxyPlayerProfile key={profilePlayer.user_id} player={profilePlayer} initialStage={profileInitialStage} onClose={() => setSelectedPlayer(null)} />}
    </div>
  );
};

export default GolaxyHomePage;
