import { useEffect, useState, type Dispatch, type SetStateAction } from 'react';
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
          setConnection({ kind: 'expired' });
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

const GolaxyHomePage = () => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [connection, setConnection] = useState<Connection>({ kind: 'loading' });
  const [retry, setRetry] = useState(0);
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
      <KioskPagebar
        backLabel={t('platform:back_to_play', '返回对弈')}
        onBack={() => navigate('/kiosk/play')}
        title={<span className="golaxy-home__title">
          <img src={PLATFORM_MARKS.golaxy.src} alt="" />
          <strong>{t('platform:golaxy', '星阵围棋')}</strong>
          {currentConnection.kind === 'connected' && <small>{t('platform:connected', '已连接')} · {currentConnection.account.saved_username || t('platform:current_golaxy_account', '当前星阵账号')}</small>}
        </span>}
        status={connected ? t('platform:connected', '已连接') : undefined}
      />

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
                <KioskCard title={t('platform:quick_match', '快速匹配')} sub={t('platform:quick_setup', '选择落子方式后匹配 →')} icon="users" onClick={() => navigate('/kiosk/play/cross-platform/golaxy/setup/quick')} />
                <KioskCard title={t('platform:rooms', '房间')} sub={t('platform:room_setup', '创建房间 / 按房号加入 →')} icon="grid-nine" onClick={() => navigate('/kiosk/play/cross-platform/golaxy/setup/room')} />
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
                <span>{t('platform:lobby_hint', '点选对局，进入只读观战')}{lists[tab] === 'ready' ? ` · ${tab === 'rooms' ? `${rooms.length} ${t('platform:games_count', '局')}` : `${users.length} ${t('platform:people_count', '人')}`}` : ''}</span>
              </div>
              <div className="golaxy-home__list-body">
              {lists[tab] === 'loading' && <p role="status" className="golaxy-home__empty">{tab === 'rooms' ? t('platform:loading_rooms', '正在读取星阵对局') : t('platform:loading_users', '正在读取在线棋友')}</p>}
              {lists[tab] === 'error' && <div className="golaxy-home__state" role="alert"><p>{tab === 'rooms' ? t('platform:rooms_failed', '没能读取星阵对局') : t('platform:users_failed', '没能读取在线棋友')}</p><button onClick={() => setListRetries((counts) => ({ ...counts, [tab]: counts[tab] + 1 }))}>{t('common:retry', '重试')}</button></div>}
              {lists[tab] === 'ready' && (tab === 'rooms' ? rooms.length === 0 : users.length === 0) && <p className="golaxy-home__empty">{tab === 'rooms' ? t('platform:no_rooms', '暂无对局') : t('platform:no_users', '暂无在线棋友')}</p>}
              {lists[tab] === 'ready' && <div className="golaxy-home__room-grid" role="tabpanel">
                {tab === 'rooms' ? rooms.map((room) => <button key={room.room_id} className="golaxy-home__room" onClick={() => navigate(`/kiosk/play/cross-platform/golaxy/spectate/${encodeURIComponent(room.room_id)}`)}>
                  <span className="golaxy-home__room-top"><b>{room.room_number ? `${room.room_number} ${t('platform:room_suffix', '房')}` : t('platform:room', '房间')}</b>{room.room_type && <span>{room.room_type}</span>}{room.handicap !== null && <span>{room.handicap === 0 ? t('platform:even_game', '分先') : room.handicap === -1 ? t('platform:black_first', '让先') : `${t('platform:handicap', '让')} ${room.handicap} ${t('platform:stones', '子')}`}</span>}{room.spectator_count !== null && <small>{room.spectator_count} {t('platform:spectators', '人观战')}</small>}</span>
                  <span className="golaxy-home__room-body">
                    <span className="golaxy-home__seat"><span className="golaxy-home__avatar">{room.black?.username.slice(0, 1) || '—'}</span><span><b>{room.black?.username || t('platform:unknown_player', '棋手信息待返回')}</b>{room.black?.rank && <small>{room.black.rank}</small>}</span></span>
                    <span className="golaxy-home__phase"><span aria-hidden="true" className="golaxy-home__mini-board" />{room.phase}</span>
                    <span className="golaxy-home__seat golaxy-home__seat--white"><span className="golaxy-home__avatar">{room.white?.username.slice(0, 1) || '—'}</span><span><b>{room.white?.username || t('platform:unknown_player', '棋手信息待返回')}</b>{room.white?.rank && <small>{room.white.rank}</small>}</span></span>
                  </span>
                </button>) : users.map((user) => <div key={user.user_id} className="golaxy-home__player"><span className="golaxy-home__avatar">{user.username.slice(0, 1)}</span><span><b>{user.username}</b>{user.rank && <small>{user.rank}</small>}</span>{user.status && <em>{user.status}</em>}</div>)}
              </div>}
              </div>
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
};

export default GolaxyHomePage;
