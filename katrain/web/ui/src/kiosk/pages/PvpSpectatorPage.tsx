import { translateResult } from '../../utils/resultTranslation';
import { interpolate } from '../utils/interpolate';
import { useTranslation } from '../../hooks/useTranslation';
import { knownRank, presentPlayerRank } from '../utils/playerRank';
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { verifiedSpectatorCount, type GameState } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { useSound } from '../../hooks/useSound';
import { formatGtpCoord } from '../../utils/gtpCoord';
import { GO_COLS } from '../shell/goBoard';
import { GoBoardSvg } from '../shell/GoBoardSvg';
import { PlayerCardSurface } from '../shell/PlayerCardSurface';
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
  player_b_rank_label?: string | null;
  player_w_rank_label?: string | null;
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
    && !!state && Array.isArray(state.board_size) && state.board_size[0] === 19 && state.board_size[1] === 19
    && Number.isSafeInteger(state.current_node_index) && state.current_node_index >= 0
    && (state.player_to_move === 'B' || state.player_to_move === 'W')
    && (state.last_move === null || point(state.last_move))
    && Array.isArray(state.stones) && state.stones.every((stone) => Array.isArray(stone)
      && (stone[0] === 'B' || stone[0] === 'W') && (stone[1] === null || point(stone[1])));
}

export default function PvpSpectatorPage() {
  const { t } = useTranslation();
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const { user, token, isAuthenticated } = useAuth();
  const { play: playSound } = useSound();
  // Scope the rendered data as well as the request: an account/room change must not paint an old board for one frame.
  const scope = JSON.stringify([sessionId, user?.id, token, isAuthenticated]);
  const [retry, setRetry] = useState(0);
  const [helpOpen, setHelpOpen] = useState(false);
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
        setView({ scope, phase: 'error', error: '请重新登录后观战。' });
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
          error: error instanceof Error ? error.message : '观战同步失败，请重试。' });
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

  const phase = snapshot ? snapshot.state.awaiting_count ? t("结算中", "结算中")
    : terminal(snapshot) ? interpolate(t("已结束{value1}", "已结束{value1}"), { value1: resultOf(snapshot) ? ` · ${translateResult(resultOf(snapshot)!, t)}` : '' }) : t("对局中", "对局中") : t("等待对局快照", "等待对局快照");
  const playing = snapshot && !snapshot.state.awaiting_count && !terminal(snapshot);
  const syncLabel = current.phase === 'ready' ? t("实时快照", "实时快照") : current.phase === 'paused' ? t("已暂停同步", "已暂停同步")
    : current.phase === 'error' ? t("同步失败", "同步失败") : t("正在同步", "正在同步");
  const stones = (color: 'B' | 'W') => snapshot?.state.stones
    .filter((stone) => stone[0] === color && stone[1] !== null)
    .map((stone) => formatGtpCoord(stone[1]![0], stone[1]![1], 19)) ?? [];
  const last = snapshot?.state.last_move;
  const spectatorCount = verifiedSpectatorCount(snapshot?.spectator_count);
  return <div className="kiosk-layout-b golaxy-spectator pvp-spectator" data-testid="pvp-spectator-page">
    <KioskPagebar backLabel={t("返回大厅", "返回大厅")} onBack={() => navigate(HOME)}
      title={<span className="golaxy-spectator__page-title">{t("大厅对局观战", "大厅对局观战")}</span>}
      status={<span className={current.phase === 'ready' ? 'golaxy-spectator__sync' : 'golaxy-spectator__info'}>{syncLabel}</span>} />
    <div className="golaxy-spectator__layout">
      <div className="golaxy-spectator__board-shell">
        {snapshot ? <div className="golaxy-spectator__board" data-testid="spectator-board">
          <div className="golaxy-spectator__ruler golaxy-spectator__ruler--top">{[...GO_COLS].map((column) => <span key={column}>{column}</span>)}</div>
          <div className="golaxy-spectator__ruler golaxy-spectator__ruler--left">{Array.from({ length: 19 }, (_, i) => <span key={i}>{19 - i}</span>)}</div>
          <GoBoardSvg size={19} black={stones('B')} white={stones('W')}
            last={last ? formatGtpCoord(last[0], last[1], 19) : undefined} label={t("大厅观战棋盘", "大厅观战棋盘")} />
        </div> : <div className="golaxy-spectator__board-state" role="status">
          {current.phase === 'error' ? t("暂无可展示的对局快照", "暂无可展示的对局快照") : current.phase === 'paused' ? t("已暂停同步", "已暂停同步") : t("正在读取对局…", "正在读取对局…")}
        </div>}
      </div>
      <aside className="golaxy-spectator__panel" aria-label={t("对局与观战信息", "对局与观战信息")}>
        <div className="golaxy-spectator__watch-head"><b>{t("在线大厅", "在线大厅")}</b><span>{t("只读观战", "只读观战")}</span><span className="golaxy-spectator__sync">{phase}</span></div>
        <div className="golaxy-spectator__clocks kiosk-player-pair">{(['b', 'w'] as const).map((color) => <div key={color}
          className={`golaxy-spectator__clock-card kiosk-player-card${playing && snapshot.state.player_to_move === color.toUpperCase() ? ' is-turn' : ''}`}>
          <PlayerCardSurface left={color === 'b'} />
          <div className="golaxy-spectator__clock-name"><i className={`golaxy-spectator__stone${color === 'w' ? ' golaxy-spectator__stone--white' : ''}`} />
            <b title={snapshot?.[`player_${color}`]}>{snapshot?.[`player_${color}`] ?? t("等待棋手信息", "等待棋手信息")}</b><span className="kiosk-player-rank">{presentPlayerRank(knownRank(snapshot?.[`player_${color}_rank_label`], '平台等级'), t).label}</span></div>
          <strong>{color === 'b' ? t("执黑", "执黑") : t("执白", "执白")}</strong>
          <small>{playing && snapshot.state.player_to_move === color.toUpperCase() ? t("轮到落子", "轮到落子") : t("对局棋手", "对局棋手")}</small>
        </div>)}</div>
        <div className="golaxy-spectator__latest" aria-live="polite"><span>
          <b>{snapshot ? interpolate(t("第 {current_node_index} 手{value2}", "第 {current_node_index} 手{value2}"), { current_node_index: snapshot.state.current_node_index, value2: last ? interpolate(t(' · 最新落子 {coord}', ' · 最新落子 {coord}'), { coord: formatGtpCoord(last[0], last[1], 19) }) : '' }) : t("等待最新盘面", "等待最新盘面")}</b>
          <small>{current.phase === 'ready' ? t("实时盘面 · 每 2 秒同步", "实时盘面 · 每 2 秒同步") : snapshot ? t("当前显示上次同步盘面", "当前显示上次同步盘面") : t("正在连接对局", "正在连接对局")}</small>
        </span></div>
        <div className="golaxy-spectator__members"><p className="golaxy-spectator__note">{spectatorCount === undefined ? t("观战人数未返回", "观战人数未返回") : interpolate(t("{spectatorCount} 人观战", "{spectatorCount} 人观战"), { spectatorCount: spectatorCount })}</p>
          <button type="button" className="pvp-spectator__help" aria-label={t("观战说明", "观战说明")} onClick={() => setHelpOpen(true)}><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v6m0-10h.01" /></svg></button>
        </div>
        {current.error && <div role="alert" className="golaxy-spectator__note">{t(current.error, current.error)} {t('当前不是实时态。', '当前不是实时态。')}</div>}
        {current.phase === 'error' && <div className="golaxy-spectator__error-actions"><button type="button" onClick={() => setRetry((n) => n + 1)}>{t("重试", "重试")}</button></div>}
      </aside>
    </div>
    {helpOpen && <div className="pvp-spectator__dialog-backdrop" onClick={() => setHelpOpen(false)}>
      <div className="pvp-spectator__dialog" role="dialog" aria-modal="true" aria-label={t("观战说明", "观战说明")} onClick={(event) => event.stopPropagation()}>
        <h2>{t("观战说明", "观战说明")}</h2><p>{t("观看实时盘面，不参与对局。此画面每 2 秒从大厅同步一次。", "观看实时盘面，不参与对局。此画面每 2 秒从大厅同步一次。")}</p>
        <button type="button" onClick={() => setHelpOpen(false)}>{t("知道了", "知道了")}</button>
      </div>
    </div>}
  </div>;
}
