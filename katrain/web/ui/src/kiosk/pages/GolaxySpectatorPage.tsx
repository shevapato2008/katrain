import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { API, ApiError, type GolaxySpectatorSnapshot } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useTranslation } from '../../hooks/useTranslation';
import { PLATFORM_MARKS } from '../constants/platformMarks';
import { GO_COLS } from '../shell/goBoard';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { KioskPagebar } from '../shell/KioskPagebar';
import '../../kiosk-shell/golaxy-spectator.css';

const HOME = '/kiosk/play/cross-platform/golaxy';
type ViewState =
  | { kind: 'loading' }
  | { kind: 'syncing' }
  | { kind: 'error'; message: string; reconnect?: boolean }
  | { kind: 'ready' | 'refreshing'; snapshot: GolaxySpectatorSnapshot; roomId: string; token: string | null | undefined };

function snapshotError(snapshot: GolaxySpectatorSnapshot, roomId: string): string | null {
  if (!snapshot || typeof snapshot !== 'object') return '星阵返回的棋谱内容不完整';
  const textOrNull = (value: unknown) => value === null || typeof value === 'string';
  const validPlayer = (value: unknown) => value === null || (
    typeof value === 'object' && value !== null && 'username' in value && typeof value.username === 'string'
    && 'rank' in value && textOrNull(value.rank)
  );
  if (typeof snapshot.room_id !== 'string' || !textOrNull(snapshot.room_number)
    || !validPlayer(snapshot.black) || !validPlayer(snapshot.white)
    || !textOrNull(snapshot.phase) || !textOrNull(snapshot.result) || !textOrNull(snapshot.room_type)
    || !(snapshot.handicap === null || Number.isSafeInteger(snapshot.handicap))) return '星阵返回的棋谱内容不完整';
  if (snapshot.room_id !== roomId) return '棋谱内容与当前房间不一致';
  if (snapshot.board_size !== 19) return '当前棋盘路数暂不支持观战';
  const validStones = (stones: unknown): stones is string[] => Array.isArray(stones) && stones.every((point) => {
    if (typeof point !== 'string' || !/^[A-HJ-T](?:[1-9]|1[0-9])$/.test(point)) return false;
    return GO_COLS.includes(point[0]) && Number(point.slice(1)) <= 19;
  });
  if (!validStones(snapshot.black_stones) || !validStones(snapshot.white_stones)
    || new Set([...snapshot.black_stones, ...snapshot.white_stones]).size !== snapshot.black_stones.length + snapshot.white_stones.length
    || !Number.isSafeInteger(snapshot.move_number) || snapshot.move_number < 0) return '星阵返回的棋谱内容不完整';
  return null;
}

const GolaxySpectatorPage = () => {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const [retry, setRetry] = useState(0);
  const [view, setView] = useState<ViewState>({ kind: 'loading' });

  useEffect(() => {
    let active = true;
    let connected = false;
    let inFlight = false;
    let requestId = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;
    const markRefreshing = (current: ViewState): ViewState => (
      (current.kind === 'ready' || current.kind === 'refreshing')
      && current.roomId === roomId && current.token === token && isAuthenticated
        ? { ...current, kind: 'refreshing' } : { kind: 'syncing' }
    );
    const stop = () => {
      clearTimeout(timer);
      timer = undefined;
      requestId += 1;
      controller?.abort();
      controller = null;
      inFlight = false;
    };
    const sync = () => {
      if (!active || !connected || document.hidden || inFlight) return;
      clearTimeout(timer);
      inFlight = true;
      const currentId = ++requestId;
      controller = new AbortController();
      let keepPolling = true;
      setView(markRefreshing);
      API.platformRoomSnapshot(roomId!, token, controller.signal).then((snapshot) => {
        if (!active || currentId !== requestId) return;
        const error = snapshotError(snapshot, roomId!);
        setView(error ? { kind: 'error', message: error } : { kind: 'ready', snapshot, roomId: roomId!, token });
      }).catch((error: unknown) => {
        if (!active || currentId !== requestId) return;
        keepPolling = !(error instanceof ApiError && (error.status === 401 || error.status === 422));
        if (!keepPolling) connected = false;
        setView(error instanceof ApiError && error.status === 401
          ? { kind: 'error', message: '星阵登录已失效', reconnect: true }
          : error instanceof ApiError && error.status === 422
            ? { kind: 'error', message: '该局型暂不支持观战' }
            : { kind: 'error', message: '没能同步星阵棋谱' });
      }).finally(() => {
        if (!active || currentId !== requestId) return;
        inFlight = false;
        controller = null;
        if (keepPolling && !document.hidden) timer = setTimeout(sync, 10_000);
      });
    };
    const onVisibilityChange = () => {
      if (document.hidden) {
        stop();
        setView((current) => current.kind === 'error' ? current : markRefreshing(current));
      } else {
        sync();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    setView({ kind: 'loading' });
    if (!roomId || !isAuthenticated) {
      setView({ kind: 'error', message: '请先连接星阵账号', reconnect: true });
      return () => { active = false; stop(); document.removeEventListener('visibilitychange', onVisibilityChange); };
    }
    API.platformStatus(token).then(({ platforms }) => {
      if (!active) return;
      if (!platforms.some((item) => item.platform === 'golaxy' && item.connected)) {
        setView({ kind: 'error', message: '星阵账号未连接', reconnect: true });
        return;
      }
      connected = true;
      setView({ kind: 'syncing' });
      sync();
    }).catch(() => {
      if (active) setView({ kind: 'error', message: '没能检查星阵连接' });
    });
    return () => { active = false; stop(); document.removeEventListener('visibilitychange', onVisibilityChange); };
  }, [roomId, isAuthenticated, token, retry]);

  const ready = (view.kind === 'ready' || view.kind === 'refreshing') && view.roomId === roomId && view.token === token && isAuthenticated
    ? view.snapshot : null;
  const player = (color: 'black' | 'white') => {
    const person = ready?.[color];
    return <span className="golaxy-spectator__player" key={color}>
      <span className={`golaxy-spectator__stone golaxy-spectator__stone--${color}`} aria-hidden="true" />
      <span>{person?.username || t('platform:unknown_player', '棋手信息待返回')}</span>
      {person?.rank && <span>{person.rank}</span>}
    </span>;
  };
  const handicap = ready?.handicap === null || ready?.handicap === undefined
    ? '让子信息待返回'
    : ready.handicap === 0 ? '分先' : ready.handicap === -1 ? '让先' : `让 ${ready.handicap} 子`;
  const goHome = () => navigate(HOME);

  return <div className="kiosk-layout-b golaxy-spectator" data-testid="golaxy-spectator-page">
    <KioskPagebar
      backLabel={t('platform:back_to_lobby', '对战大厅')}
      onBack={goHome}
      title={<span className="golaxy-spectator__page-title"><img src={PLATFORM_MARKS.golaxy.src} alt="" />{t('platform:spectate', '对局观战')}</span>}
      status={view.kind === 'refreshing' ? t('platform:syncing', '同步中') : ready ? t('platform:read_only', '只读观战') : view.kind === 'error' ? t('platform:sync_failed', '同步失败') : t('platform:syncing', '同步中')}
    />
    <h1 className="golaxy-spectator__heading">
      {ready?.room_number ? `${ready.room_number} 房 · ` : ''}{t('platform:spectate', '对局观战')}
      <small>{t('platform:snapshot_auto', '每 10 秒自动同步星阵棋谱 · 只读观战')}</small>
    </h1>
    <div className="golaxy-spectator__layout">
      <div className="golaxy-spectator__board-shell">
        {ready ? <><div className="golaxy-spectator__board" data-testid="spectator-board">
          <GoBoardSvg size={19} black={ready.black_stones} white={ready.white_stones} label={t('platform:spectator_board', '星阵观战棋盘')} />
        </div><small>{ready.move_number} {t('platform:moves_suffix', '手')} · {t('platform:snapshot_board', '星阵棋谱快照')}</small></> :
          <div className="golaxy-spectator__board-state" role={view.kind === 'error' ? 'alert' : 'status'}>
            {view.kind === 'error' ? view.message : view.kind === 'syncing' ? '正在同步星阵棋谱' : '正在检查星阵连接'}
          </div>}
      </div>
      <div className="golaxy-spectator__panel">
        <span className="golaxy-spectator__label">{ready?.result ? '对局结果' : ready?.phase || '对局状态待返回'}</span>
        <div className="golaxy-spectator__value golaxy-spectator__players">
          {ready ? <>{player('black')}{player('white')}</> : '等待星阵棋谱'}
        </div>
        <span className="golaxy-spectator__label">对局信息</span>
        <div className="golaxy-spectator__value">
          {ready ? `${ready.room_type || '对局类型待返回'} · ${handicap} · ${ready.board_size} 路 · ${ready.move_number} 手` : '同步成功后显示对局信息'}
        </div>
        {ready && <p className="golaxy-spectator__note">{view.kind === 'refreshing' ? '正在同步，当前为上次快照'
          : ready.phase === '已结束' && !ready.result ? '胜负结果尚未返回'
            : `${ready.result || ready.phase || '对局状态待返回'} · 棋谱每 10 秒自动同步。`}</p>}
        {view.kind === 'error' && <div className="golaxy-spectator__error-actions">
          <p>{view.reconnect ? '请重新连接星阵后返回观战。' : '本页没有可展示的棋盘。'}</p>
          <button type="button" onClick={() => view.reconnect ? navigate('/kiosk/play/cross-platform/login/golaxy') : setRetry((count) => count + 1)}>{view.reconnect ? '重新连接' : '重试'}</button>
        </div>}
        <button type="button" className="golaxy-spectator__return" onClick={goHome}>返回对战大厅</button>
      </div>
    </div>
  </div>;
};

export default GolaxySpectatorPage;
