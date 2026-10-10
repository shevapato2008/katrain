import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { API, ApiError, type GolaxySpectatorPosition, type GolaxySpectatorSnapshot } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useSound } from '../../hooks/useSound';
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

const sameStones = (left: string[], right: string[]) => left.length === right.length && left.every((stone, index) => stone === right[index]);
const samePosition = (left: GolaxySpectatorPosition, right: GolaxySpectatorPosition) => (
  left.move_number === right.move_number
  && sameStones(left.black_stones, right.black_stones)
  && sameStones(left.white_stones, right.white_stones)
  && left.last_move?.color === right.last_move?.color
  && left.last_move?.coordinate === right.last_move?.coordinate
);
const sameHistoryPrefix = (left: GolaxySpectatorSnapshot, right: GolaxySpectatorSnapshot) => {
  const lastSharedMove = Math.min(left.move_number, right.move_number);
  return left.history.slice(0, lastSharedMove + 1).every((position, index) => samePosition(position, right.history[index]));
};

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
  if (!(snapshot.game_id === null || (typeof snapshot.game_id === 'string' && /^[1-9]\d*$/.test(snapshot.game_id))))
    return '星阵返回的棋谱内容不完整';
  const validStones = (stones: unknown): stones is string[] => Array.isArray(stones) && stones.every((point) => {
    if (typeof point !== 'string' || !/^[A-HJ-T](?:[1-9]|1[0-9])$/.test(point)) return false;
    return GO_COLS.includes(point[0]) && Number(point.slice(1)) <= 19;
  });
  const validPosition = (entry: unknown): entry is GolaxySpectatorPosition => {
    if (!entry || typeof entry !== 'object') return false;
    const position = entry as GolaxySpectatorPosition;
    if (!Number.isSafeInteger(position.move_number) || position.move_number < 0
      || !validStones(position.black_stones) || !validStones(position.white_stones)
      || new Set([...position.black_stones, ...position.white_stones]).size !== position.black_stones.length + position.white_stones.length)
      return false;
    const move = position.last_move;
    return move === null || (move && (move.color === 'B' || move.color === 'W')
      && (move.coordinate === null || (typeof move.coordinate === 'string'
        && validStones([move.coordinate]))));
  };
  if (!validPosition(snapshot) || !Array.isArray(snapshot.history)
    || snapshot.history.length !== snapshot.move_number + 1) return '星阵返回的棋谱内容不完整';
  for (let index = 0; index < snapshot.history.length; index += 1) {
    const entry: unknown = snapshot.history[index];
    if (!validPosition(entry) || entry.move_number !== index) return '星阵返回的棋谱内容不完整';
    if (index === 0) {
      if (entry.last_move !== null || entry.black_stones.length || entry.white_stones.length) return '星阵返回的棋谱内容不完整';
      continue;
    }
    const move = entry.last_move;
    if (!move || move.color !== (index % 2 ? 'B' : 'W')) return '星阵返回的棋谱内容不完整';
    const previous = snapshot.history[index - 1];
    if (move.coordinate === null) {
      if (!sameStones(entry.black_stones, previous.black_stones)
        || !sameStones(entry.white_stones, previous.white_stones)) return '星阵返回的棋谱内容不完整';
    } else if (!(move.color === 'B' ? entry.black_stones : entry.white_stones).includes(move.coordinate)) {
      return '星阵返回的棋谱内容不完整';
    }
  }
  if (!samePosition(snapshot, snapshot.history.at(-1)!)) return '星阵返回的棋谱内容不完整';
  return null;
}

const GolaxySpectatorPage = () => {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { token, isAuthenticated } = useAuth();
  const { play: playSound } = useSound();
  const [soundOn, setSoundOn] = useState(true);
  const [historyMove, setHistoryMove] = useState<number | null>(null);
  const soundOnRef = useRef(soundOn);
  const historyMoveRef = useRef(historyMove);
  soundOnRef.current = soundOn;
  historyMoveRef.current = historyMove;
  const [retry, setRetry] = useState(0);
  const [view, setView] = useState<ViewState>({ kind: 'loading' });

  useEffect(() => {
    let active = true;
    let connected = false;
    let inFlight = false;
    let requestId = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | null = null;
    let previousSnapshot: GolaxySpectatorSnapshot | null = null;
    let suppressNextSound = true;
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
      let nextPollDelay = 2_000;
      setView(markRefreshing);
      API.platformRoomSnapshot(roomId!, token, controller.signal).then((snapshot) => {
        if (!active || currentId !== requestId) return;
        const error = snapshotError(snapshot, roomId!);
        if (error) {
          suppressNextSound = true;
          nextPollDelay = 10_000;
          setView({ kind: 'error', message: error });
          return;
        }
        const prior = previousSnapshot;
        const sameGame = prior !== null && prior.game_id === snapshot.game_id && sameHistoryPrefix(prior, snapshot);
        const regressed = sameGame && snapshot.move_number < prior.move_number;
        if (prior && (!sameGame || regressed)) setHistoryMove(null);
        if (sameGame && snapshot.move_number > prior.move_number && snapshot.last_move?.coordinate
          && !suppressNextSound && !document.hidden && historyMoveRef.current === null && soundOnRef.current) {
          playSound('stone');
        }
        if (!regressed) previousSnapshot = snapshot;
        suppressNextSound = false;
        setView({ kind: 'ready', snapshot, roomId: roomId!, token });
      }).catch((error: unknown) => {
        if (!active || currentId !== requestId) return;
        suppressNextSound = true;
        nextPollDelay = 10_000;
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
        if (keepPolling && !document.hidden) timer = setTimeout(sync, nextPollDelay);
      });
    };
    const onVisibilityChange = () => {
      if (document.hidden) {
        stop();
        suppressNextSound = true;
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
  }, [roomId, isAuthenticated, token, retry, playSound]);

  const ready = (view.kind === 'ready' || view.kind === 'refreshing') && view.roomId === roomId && view.token === token && isAuthenticated
    ? view.snapshot : null;
  useEffect(() => { setHistoryMove(null); }, [roomId, token]);
  const position = historyMove === null ? ready : ready?.history[historyMove] || ready;
  const lastMove = ready?.last_move;
  const earlier = position && position.move_number > 0 ? ready?.history[position.move_number - 1] : null;
  const formatClock = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
  const clockCard = (color: 'black' | 'white') => {
    const person = ready?.[color]; const clock = ready?.clocks?.[color];
    const active = ready?.clocks?.active_color === (color === 'black' ? 'B' : 'W');
    return <div className={`golaxy-spectator__clock-card${active ? ' is-turn' : ''}`} key={color}>
      <div className="golaxy-spectator__clock-name"><i className={`golaxy-spectator__stone golaxy-spectator__stone--${color}`} /><b>{color === 'black' ? '黑' : '白'} · <span>{person?.username || t('platform:unknown_player', '棋手信息待返回')}</span></b>{person?.rank && <span>{person.rank}</span>}</div>
      <strong>{clock && Number.isFinite(clock.remaining_seconds) && clock.remaining_seconds >= 0 ? formatClock(clock.remaining_seconds) : '—'}</strong>
      <small>{clock ? clock.period_seconds != null && clock.periods_remaining != null ? `读秒 ${clock.period_seconds} 秒 · 剩余 ${clock.periods_remaining} 次` : '星阵时钟快照' : '计时信息未返回'}</small>
    </div>;
  };
  const handicap = ready?.handicap === null || ready?.handicap === undefined
    ? '让子信息待返回'
    : ready.handicap === 0 ? '分先' : ready.handicap === -1 ? '让先' : `让 ${ready.handicap} 子`;
  const goHome = () => navigate(HOME);

  return <div className="kiosk-layout-b golaxy-spectator" data-testid="golaxy-spectator-page">
    <KioskPagebar
      backLabel={<><span className="golaxy-spectator__sr-only">返回</span>{t('platform:back_to_lobby', '对战大厅')}</>}
      onBack={goHome}
      title={<span className="golaxy-spectator__page-title"><img src={PLATFORM_MARKS.golaxy.src} alt="" />{ready?.room_number ? `${ready.room_number} 房 · ` : ''}{t('platform:spectate', '对局观战')}</span>}
      status={<><span className="golaxy-spectator__info">{ready && `${ready.room_type || '对局类型待返回'} · ${handicap} · 19 路`}</span><span className="golaxy-spectator__sync">{view.kind === 'error' ? '同步失败' : '快照同步'}</span></>}
    />
    <div className="golaxy-spectator__layout">
      <div className="golaxy-spectator__board-shell">
        {ready && position ? <><div className="golaxy-spectator__board" data-testid="spectator-board">
          <div className="golaxy-spectator__ruler golaxy-spectator__ruler--top">{[...GO_COLS].map((column) => <span key={column}>{column}</span>)}</div>
          <div className="golaxy-spectator__ruler golaxy-spectator__ruler--left">{Array.from({ length: 19 }, (_, i) => <span key={i}>{19 - i}</span>)}</div>
          <GoBoardSvg size={19} black={position.black_stones} white={position.white_stones} last={position.last_move?.coordinate || undefined} label={t('platform:spectator_board', '星阵观战棋盘')} />
        </div><small className="golaxy-spectator__sr-only">{position.move_number} {t('platform:moves_suffix', '手')} · 星阵棋谱快照</small></> :
          <div className="golaxy-spectator__board-state" role={view.kind === 'error' ? 'alert' : 'status'}>
            {view.kind === 'error' ? view.message : view.kind === 'syncing' ? '正在同步星阵棋谱' : '正在检查星阵连接'}
          </div>}
      </div>
      <aside className="golaxy-spectator__panel" aria-label="对局与观战信息">
        <div className="golaxy-spectator__watch-head"><b>{ready?.room_number ? `${ready.room_number} 房` : '对局状态'}</b><span>{ready ? `${ready.room_type || '类型未返回'} · ${handicap}` : '等待星阵棋谱'}</span><span className="golaxy-spectator__sync">{ready?.result || ready?.phase || '同步中'}</span></div>
        <div className="golaxy-spectator__clocks">{clockCard('black')}{clockCard('white')}</div>
        <div className="golaxy-spectator__latest" aria-live="polite"><span className="golaxy-spectator__latest-dot">•</span><span><b>{ready ? lastMove ? `最新：${lastMove.color === 'B' ? '黑' : '白'} ${lastMove.coordinate || '停一手'} · 第 ${ready.move_number} 手` : `第 ${ready.move_number} 手 · 暂无落子` : '等待星阵最新落子'}</b><small>{historyMove !== null ? '回看棋谱时仍接收新快照' : view.kind === 'refreshing' ? '正在同步，当前为上次快照' : ready?.phase === '已结束' && !ready.result ? '胜负结果尚未返回' : '星阵棋谱快照 · 每 2 秒同步'}</small></span></div>
        <div className="golaxy-spectator__members-head"><strong>房间成员</strong><span>{ready?.members ? `对局双方与观战棋友 · ${ready.members.length} 人` : '成员信息未返回'}</span></div>
        <div className="golaxy-spectator__members">{ready?.members ? ready.members.map((member) => <div className="golaxy-spectator__member" key={member.user_id}><span className="golaxy-spectator__avatar">{member.username.slice(-1)}</span><b>{member.username}</b><small>{member.role === 'black' ? '对局 · 黑' : member.role === 'white' ? '对局 · 白' : member.role === 'spectator' ? '观战' : '身份未返回'}</small></div>) : <p className="golaxy-spectator__note">星阵尚未提供可展示的房间成员名单。</p>}</div>
        {view.kind === 'error' && <div className="golaxy-spectator__error-actions"><button type="button" onClick={() => view.reconnect ? navigate('/kiosk/play/cross-platform/login/golaxy') : setRetry((count) => count + 1)}>{view.reconnect ? '重新连接' : '重试'}</button></div>}
        <div className="golaxy-spectator__footer"><button type="button" aria-pressed={soundOn} onClick={() => setSoundOn(!soundOn)}>落子音：{soundOn ? '开' : '关'}</button><button type="button" disabled={!earlier} title={!earlier ? '已经是第一手之前' : undefined} onClick={() => earlier && setHistoryMove(earlier.move_number)}>上一手</button><button className="golaxy-spectator__return-live" disabled={historyMove === null || !ready} onClick={() => setHistoryMove(null)}>{historyMove !== null ? '回到最新' : '正在看最新'}{ready ? ` · ${ready.move_number} 手` : ''}</button></div>
      </aside>
    </div>
  </div>;
};

export default GolaxySpectatorPage;
