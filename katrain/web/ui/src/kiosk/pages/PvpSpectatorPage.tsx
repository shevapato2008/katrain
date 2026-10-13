import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { verifiedSpectatorCount, type GameState } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useSound } from '../../hooks/useSound';
import { formatGtpCoord } from '../../utils/gtpCoord';
import { GO_COLS } from '../shell/goBoard';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { KioskPagebar } from '../shell/KioskPagebar';
import '../../kiosk-shell/golaxy-spectator.css';

type Snapshot = {
  session_id: string;
  public_lobby: true;
  game_ended: boolean;
  spectator_count?: number;
  player_b: string;
  player_w: string;
  player_b_id: number;
  player_w_id: number;
  player_b_rank_label: string | null;
  player_w_rank_label: string | null;
  state: Pick<GameState, 'game_id' | 'board_size' | 'stones' | 'last_move' | 'current_node_index' | 'player_to_move'
    | 'end_result' | 'terminal_result' | 'awaiting_count'>;
};
type View = {
  scope: string;
  phase: 'loading' | 'syncing' | 'ready' | 'paused' | 'error';
  snapshot?: Snapshot;
  error?: string;
};
const HOME = '/kiosk/play/pvp/lobby';
const resultOf = (snapshot: Snapshot) => snapshot.state.terminal_result || snapshot.state.end_result;
const terminal = (snapshot: Snapshot) => !snapshot.state.awaiting_count && (snapshot.game_ended || !!resultOf(snapshot));

function validSnapshot(value: unknown, sessionId: string): value is Snapshot {
  if (!value || typeof value !== 'object') return false;
  const snapshot = value as Snapshot;
  const state = snapshot.state;
  const point = (coords: unknown) => Array.isArray(coords) && coords.length === 2
    && coords.every((n) => Number.isInteger(n) && n >= 0 && n < 19);
  return snapshot.session_id === sessionId && snapshot.public_lobby === true && typeof snapshot.game_ended === 'boolean'
    && typeof snapshot.player_b === 'string' && typeof snapshot.player_w === 'string'
    && Number.isSafeInteger(snapshot.player_b_id) && Number.isSafeInteger(snapshot.player_w_id)
    && [snapshot.player_b_rank_label, snapshot.player_w_rank_label].every((label) => label === null || typeof label === 'string')
    && !!state && Array.isArray(state.board_size) && state.board_size[0] === 19 && state.board_size[1] === 19
    && Number.isSafeInteger(state.current_node_index) && state.current_node_index >= 0
    && (state.player_to_move === 'B' || state.player_to_move === 'W')
    && (state.last_move === null || point(state.last_move))
    && Array.isArray(state.stones) && state.stones.every((stone) => Array.isArray(stone)
      && (stone[0] === 'B' || stone[0] === 'W') && (stone[1] === null || point(stone[1])));
}

export default function PvpSpectatorPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { user, token, isAuthenticated } = useAuth();
  const { play: playSound } = useSound();
  // Scope the rendered data as well as the request: an account/room change must not paint an old board for one frame.
  const scope = JSON.stringify([sessionId, user?.id, token, isAuthenticated]);
  const [retry, setRetry] = useState(0);
  const [view, setView] = useState<View>({ scope, phase: 'loading' });
  const viewRef = useRef(view);
  const soundFrontierRef = useRef<{ scope: string; snapshot: Snapshot } | null>(null);
  viewRef.current = view;
  const current = view.scope === scope ? view : { scope, phase: 'loading' as const };
  const snapshot = current.snapshot;

  useEffect(() => {
    let active = true;
    let inFlight = false;
    let sequence = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    let previous = viewRef.current.scope === scope ? viewRef.current.snapshot : undefined;
    let soundFrontier = soundFrontierRef.current?.scope === scope ? soundFrontierRef.current.snapshot : undefined;
    let suppressNextSound = true;
    const isVisible = () => document.visibilityState !== 'hidden';
    setView({ scope, phase: 'loading', snapshot: previous });
    const stop = () => {
      clearTimeout(timer);
      sequence += 1;
      controller?.abort();
      inFlight = false;
    };
    const sync = async () => {
      if (!active || inFlight || document.visibilityState === 'hidden') return;
      if (!isAuthenticated || !sessionId) {
        setView({ scope, phase: 'error', error: '请重新登录后观战。当前不是实时态。' });
        return;
      }
      inFlight = true;
      const request = ++sequence;
      controller = new AbortController();
      setView({ scope, phase: 'syncing', snapshot: previous });
      const isCurrent = () => active && request === sequence;
      try {
        const response = await fetch(`/api/pvp/spectate/${encodeURIComponent(sessionId)}`, {
          method: 'GET', credentials: 'same-origin', signal: controller.signal,
          headers: token ? { Authorization: `Bearer ${token}` } : undefined,
        });
        if (!isCurrent()) return;
        if (!response.ok) {
          const message = response.status === 401 ? '登录状态已失效，请重新登录。'
            : response.status === 404 ? previous && terminal(previous)
              ? '对局已结束，已保留最后终局。' : '对局不存在或已结束。'
              : '观战同步失败，请重试。';
          throw new Error(message);
        }
        const data: unknown = await response.json();
        if (!isCurrent()) return;
        if (!validSnapshot(data, sessionId)) throw new Error('观战快照内容不完整，请重试。');
        const sameGame = !!soundFrontier && soundFrontier.state.game_id === data.state.game_id;
        const advanced = !!soundFrontier && data.state.current_node_index > soundFrontier.state.current_node_index;
        if (sameGame && advanced && !suppressNextSound && isVisible() && data.state.last_move) {
          playSound('stone');
        }
        // Keep the furthest observed move through an older response, so receiving
        // the same live stone again after a rewind cannot sound twice.
        if (!sameGame || advanced) {
          soundFrontier = data;
          soundFrontierRef.current = { scope, snapshot: data };
        }
        suppressNextSound = false;
        previous = data;
        setView({ scope, phase: 'ready', snapshot: data });
        timer = setTimeout(() => { void sync(); }, 2000);
      } catch (error) {
        if (!isCurrent()) return;
        suppressNextSound = true;
        setView({ scope, phase: 'error', snapshot: previous,
          error: `${error instanceof Error ? error.message : '观战同步失败，请重试。'} 当前不是实时态。` });
      } finally {
        if (isCurrent()) inFlight = false;
      }
    };
    const visibility = () => {
      stop();
      if (document.visibilityState === 'hidden') {
        suppressNextSound = true;
        setView({ scope, phase: 'paused', snapshot: previous });
      }
      else void sync();
    };
    document.addEventListener('visibilitychange', visibility);
    if (document.visibilityState === 'hidden') setView({ scope, phase: 'paused', snapshot: previous });
    else void sync();
    return () => { active = false; stop(); document.removeEventListener('visibilitychange', visibility); };
  }, [sessionId, user?.id, token, isAuthenticated, scope, retry, playSound]);

  const phase = snapshot ? snapshot.state.awaiting_count ? '结算中'
    : terminal(snapshot) ? `已结束${resultOf(snapshot) ? ` · ${resultOf(snapshot)}` : ''}` : '对局中' : '等待对局快照';
  const playing = snapshot && !snapshot.state.awaiting_count && !terminal(snapshot);
  const syncLabel = current.phase === 'ready' ? '实时快照' : current.phase === 'paused' ? '已暂停同步'
    : current.phase === 'error' ? '同步失败' : '正在同步';
  const stones = (color: 'B' | 'W') => snapshot?.state.stones
    .filter((stone) => stone[0] === color && stone[1] !== null)
    .map((stone) => formatGtpCoord(stone[1]![0], stone[1]![1], 19)) ?? [];
  const last = snapshot?.state.last_move;
  const spectatorCount = verifiedSpectatorCount(snapshot?.spectator_count);
  return <div className="kiosk-layout-b golaxy-spectator" data-testid="pvp-spectator-page">
    <KioskPagebar backLabel="返回大厅" onBack={() => navigate(HOME)}
      title={<span className="golaxy-spectator__page-title">大厅对局观战</span>}
      status={<><span className="golaxy-spectator__info">只读观战 · 19 路</span><span className={current.phase === 'ready' ? 'golaxy-spectator__sync' : 'golaxy-spectator__info'}>{syncLabel}</span></>} />
    <div className="golaxy-spectator__layout">
      <div className="golaxy-spectator__board-shell">
        {snapshot ? <div className="golaxy-spectator__board" data-testid="spectator-board">
          <div className="golaxy-spectator__ruler golaxy-spectator__ruler--top">{[...GO_COLS].map((column) => <span key={column}>{column}</span>)}</div>
          <div className="golaxy-spectator__ruler golaxy-spectator__ruler--left">{Array.from({ length: 19 }, (_, i) => <span key={i}>{19 - i}</span>)}</div>
          <GoBoardSvg size={19} black={stones('B')} white={stones('W')}
            last={last ? formatGtpCoord(last[0], last[1], 19) : undefined} label="大厅观战棋盘" />
        </div> : <div className="golaxy-spectator__board-state" role="status">
          {current.phase === 'error' ? '暂无可展示的对局快照' : current.phase === 'paused' ? '已暂停同步' : '正在读取对局…'}
        </div>}
      </div>
      <aside className="golaxy-spectator__panel" aria-label="对局与观战信息">
        <div className="golaxy-spectator__watch-head"><b>在线大厅</b><span>只读观战</span><span className="golaxy-spectator__sync">{phase}</span></div>
        <div className="golaxy-spectator__clocks">{(['b', 'w'] as const).map((color) => <div key={color}
          className={`golaxy-spectator__clock-card${playing && snapshot.state.player_to_move === color.toUpperCase() ? ' is-turn' : ''}`}>
          <div className="golaxy-spectator__clock-name"><i className={`golaxy-spectator__stone${color === 'w' ? ' golaxy-spectator__stone--white' : ''}`} />
            <b>{snapshot?.[`player_${color}`] ?? '等待棋手信息'}</b><span>{color === 'b' ? '执黑' : '执白'}</span></div>
          <strong>{snapshot?.[`player_${color}_rank_label`] ?? (snapshot ? '尚未定级' : '—')}</strong>
          <small>{playing && snapshot.state.player_to_move === color.toUpperCase() ? '轮到落子' : '对局棋手'}</small>
        </div>)}</div>
        <div className="golaxy-spectator__latest" aria-live="polite"><span className="golaxy-spectator__latest-dot">•</span><span>
          <b>{snapshot ? `第 ${snapshot.state.current_node_index} 手${last ? ` · 最新落子 ${formatGtpCoord(last[0], last[1], 19)}` : ''}` : '等待最新盘面'}</b>
          <small>{current.phase === 'ready' ? '实时盘面 · 每 2 秒同步' : snapshot ? '当前显示上次同步盘面' : '正在连接对局'}</small>
        </span></div>
        <div className="golaxy-spectator__members"><p className="golaxy-spectator__note">{spectatorCount === undefined ? '观战人数未返回' : `${spectatorCount} 人观战`}</p><p className="golaxy-spectator__note">观看实时盘面，不参与对局。</p></div>
        {current.error && <div role="alert" className="golaxy-spectator__note">{current.error}</div>}
        {current.phase === 'error' && <div className="golaxy-spectator__error-actions"><button type="button" onClick={() => setRetry((n) => n + 1)}>重试</button></div>}
      </aside>
    </div>
  </div>;
}
