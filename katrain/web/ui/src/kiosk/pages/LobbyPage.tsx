import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { verifiedSpectatorCount } from '../../api';
import { useAuth } from '../../context/AuthContext';
import { getAiLadderStatus } from '../../features/aiLadder/api';
import { websocketUrl } from '../../utils/websocketUrl';
import { isStrictBoxKiosk } from '../shell/boxUrls';
import './LobbyPage.css';

type Person = { id: number; username: string; ladder_rung: number | null; rank_label: string | null; presence: 'idle' | 'playing' };
type Game = { session_id: string; player_b: string; player_w: string; player_b_id?: number; player_w_id?: number; player_b_rank_label?: string | null; player_w_rank_label?: string | null; move_count: number; spectator_count?: number };
const isPerson = (v: unknown): v is Person => !!v && typeof v === 'object' && typeof (v as Person).id === 'number' && typeof (v as Person).username === 'string';
const isGame = (v: unknown): v is Game => !!v && typeof v === 'object' && typeof (v as Game).session_id === 'string' && typeof (v as Game).player_b === 'string' && typeof (v as Game).player_w === 'string';
const BACK = { backTo: '/kiosk/play/pvp/lobby' };
const Stone = ({ color }: { color: 'black' | 'white' }) => <span className={`pvp-kiosk__stone pvp-kiosk__stone--${color}`} aria-hidden="true" />;
const Eye = () => <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" /><circle cx="12" cy="12" r="2.5" /></svg>;
function LobbyDialog({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  const modal = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    modal.current?.focus();
    return () => { if (previous?.isConnected) previous.focus(); };
  }, []);
  return <div className="pvp-kiosk__layer"><section ref={modal} role="dialog" aria-modal="true" aria-labelledby="pvp-dialog-title" tabIndex={-1}
    onKeyDown={(event) => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); onClose(); }
      if (event.key !== 'Tab') return;
      const controls = [...(modal.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? [])];
      const first = controls[0]; const last = controls.at(-1);
      if (event.shiftKey && (document.activeElement === first || document.activeElement === modal.current)) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === modal.current)) { event.preventDefault(); first?.focus(); }
    }}><h2 id="pvp-dialog-title">{title}</h2>{children}</section></div>;
}
export default function LobbyPage() {
  const navigate = useNavigate();
  const { user, token, isAuthenticated } = useAuth();
  const scope = JSON.stringify([isAuthenticated, user?.id, token]);
  const scopeRef = useRef(scope); scopeRef.current = scope;
  const [identityScope, setIdentityScope] = useState(scope);
  const [identityId, setCentralId] = useState<number | null>(isStrictBoxKiosk ? null : user?.id ?? null);
  const centralId = !isStrictBoxKiosk ? user?.id ?? null : identityScope === scope ? identityId : null;
  const [identityError, setIdentityError] = useState(false);
  const [lists, setLists] = useState<{ scope: string; users: Person[]; games: Game[]; loaded: boolean; error: boolean }>({ scope, users: [], games: [], loaded: false, error: false });
  const { users, games, loaded, error: loadError } = lists.scope === scope ? lists : { users: [], games: [], loaded: false, error: false };
  const listRequest = useRef(0);
  const listAbort = useRef<AbortController | null>(null);
  const [tab, setTab] = useState<'games' | 'players'>('games');
  const [outgoing, setOutgoing] = useState<Person | null>(null);
  const inviteSent = useRef(false);
  const focusPlayers = useRef(false);
  const [rank, setRank] = useState<{ rung: number; label: string } | null>(null);
  const [rankLoaded, setRankLoaded] = useState(false);
  const [rankError, setRankError] = useState(false);
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [filter, setFilter] = useState<'all' | 'same'>('all');
  const [dialog, setDialog] = useState<'placement' | 'matching' | null>(null);
  const [invite, setInvite] = useState<{ from_id: number; from_name: string } | null>(null);
  const [notice, setNotice] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [retryEpoch, setRetryEpoch] = useState(0);
  const socket = useRef<WebSocket | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const rankRequest = useRef(0);
  const peersRef = useRef<HTMLDivElement>(null);
  const clearTimer = () => { if (timer.current) clearInterval(timer.current); timer.current = null; };
  const fetchLists = useCallback(async () => {
    if (!isAuthenticated) return;
    const request = ++listRequest.current;
    listAbort.current?.abort();
    const controller = new AbortController(); listAbort.current = controller;
    const current = () => request === listRequest.current && scopeRef.current === scope;
    try {
      const [u, g] = await Promise.all([
        fetch('/api/v1/users/online', { signal: controller.signal, headers: token ? { Authorization: `Bearer ${token}` } : undefined }),
        fetch('/api/v1/games/active/multiplayer', { signal: controller.signal, headers: token ? { Authorization: `Bearer ${token}` } : undefined }),
      ]);
      if (!u.ok || !g.ok) throw new Error();
      const [uRows, gRows]: unknown[] = await Promise.all([u.json(), g.json()]);
      if (current()) setLists({ scope, users: Array.isArray(uRows) ? uRows.filter(isPerson) : [], games: Array.isArray(gRows) ? gRows.filter(isGame) : [], loaded: true, error: false });
    } catch {
      if (current()) setLists({ scope, users: [], games: [], loaded: true, error: true });
    }
  }, [isAuthenticated, token, scope]);
  useEffect(() => {
    setIdentityScope(scope);
    setIdentityError(false);
    if (!isAuthenticated) { setCentralId(null); return; }
    if (!isStrictBoxKiosk) { setCentralId(user?.id ?? null); return; }
    let cancelled = false;
    setCentralId(null);
    setIdentityError(false);
    fetch('/api/pvp/identity', { headers: token ? { Authorization: `Bearer ${token}` } : undefined, credentials: 'same-origin' })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data: unknown) => {
        const id = data && typeof data === 'object' ? (data as Record<string, unknown>).user_id : null;
        if (typeof id !== 'number' || !Number.isFinite(id)) throw new Error();
        if (!cancelled) {
          setCentralId(id);
          setIdentityError(false);
        }
      }).catch(() => { if (!cancelled) { setCentralId(null); setIdentityError(true); } });
    return () => { cancelled = true; };
  }, [isAuthenticated, token, user?.id, scope, retryEpoch]);
  const loadRank = useCallback(async () => {
    if (!isAuthenticated) return;
    const request = ++rankRequest.current;
    setRankLoaded(false);
    setRankError(false);
    try {
      const status = await getAiLadderStatus(token ?? undefined);
      const placement = status?.placement_state;
      if (placement?.phase === 'placed' && typeof placement.rung?.rung === 'number'
        && typeof placement.rung.rank_name === 'string') {
        if (request === rankRequest.current) setRank({ rung: placement.rung.rung, label: placement.rung.rank_name });
      } else if (placement?.phase === 'placement') {
        if (request === rankRequest.current) setRank(null);
      } else throw new Error('Invalid rank status');
    } catch {
      if (request === rankRequest.current) { setRank(null); setRankError(true); }
    } finally { if (request === rankRequest.current) setRankLoaded(true); }
  }, [isAuthenticated, token]);
  useEffect(() => { setRank(null); setFilter('all'); setDialog(null); setOutgoing(null); setInvite(null); setNotice(''); void loadRank(); return () => { rankRequest.current++; }; }, [loadRank, user?.id, retryEpoch]);
  useEffect(() => { if (tab === 'players' && focusPlayers.current) { focusPlayers.current = false; peersRef.current?.focus(); } }, [tab]);
  useEffect(() => {
    setLists({ scope, users: [], games: [], loaded: false, error: false });
    if (!isAuthenticated) return;
    void fetchLists();
    const refresh = setInterval(() => { void fetchLists(); }, 10000);
    let stopped = false;
    let authRejected = false;
    let reconnect: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 1000;
    const connect = () => {
      if (stopped) return;
      const ws = new WebSocket(websocketUrl('/ws/lobby', token));
      socket.current = ws;
      const current = () => !stopped && socket.current === ws;
      ws.onopen = () => { if (current()) setConnection('connected'); };
      ws.onclose = (event) => {
        if (!current()) return;
        socket.current = null;
        setConnection('disconnected');
        setDialog((d) => d === 'matching' ? null : d);
        clearTimer();
        // A central release closes the upstream socket (1012 -> box 1013).
        // Reconnect the lobby only; never replay a match request or invitation.
        if (!authRejected && event.code !== 1008) {
          reconnect = setTimeout(() => { reconnect = null; connect(); }, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 15000);
        }
      };
      ws.onerror = () => { if (current()) setConnection('disconnected'); };
      ws.onmessage = (event) => {
        if (!current()) return;
        let data: Record<string, unknown>;
        try { data = JSON.parse(event.data); } catch { return; }
        if (data.type === 'match_found' && typeof data.session_id === 'string') {
          clearTimer(); setDialog(null); navigate(`/kiosk/play/pvp/room/${data.session_id}`, { state: BACK });
        } else if (data.type === 'lobby_update') {
          retryDelay = 1000;
          void fetchLists();
        } else if (data.type === 'invitation') setInvite({ from_id: Number(data.from_id), from_name: String(data.from_name) });
        else if (data.type === 'error') {
          clearTimer();
          if (data.code === 'PLACEMENT_REQUIRED') setDialog('placement');
          else if (data.code === 'CENTRAL_DISCONNECTED') {
            setDialog(null); setConnection('disconnected');
          } else {
            if (data.code === 'BOX_SESSION_REVOKED') authRejected = true;
            setDialog(null); setNotice(data.code === 'INVITE_NOT_PENDING' ? '邀请已过期，请对方重新邀请。' : String(data.message || '操作失败，请重试。'));
          }
        } else if (data.type === 'info') setNotice(String(data.message || ''));
      };
    };
    setConnection('connecting');
    connect();
    return () => {
      stopped = true;
      listRequest.current++; listAbort.current?.abort();
      if (reconnect) clearTimeout(reconnect);
      const ws = socket.current;
      if (ws) { ws.onopen = null; ws.onclose = null; ws.onerror = null; ws.onmessage = null; ws.close(); }
      socket.current = null;
      clearInterval(refresh); clearTimer();
    };
  }, [isAuthenticated, token, user?.id, fetchLists, navigate, scope, retryEpoch]);
  const retryLobby = () => {
    setNotice('');
    setConnection('connecting');
    setLists({ scope, users: [], games: [], loaded: false, error: false });
    setRetryEpoch((n) => n + 1);
  };
  const send = (message: Record<string, unknown>) => {
    if (socket.current?.readyState !== WebSocket.OPEN) { setNotice('大厅连接已断开，请稍后重试。'); return false; }
    socket.current.send(JSON.stringify(message)); return true;
  };
  const start = () => {
    if (!rankLoaded || rankError || centralId === null) return;
    if (!rank) { setDialog('placement'); return; }
    if (!send({ type: 'start_matchmaking' })) return;
    clearTimer(); setElapsed(0); timer.current = setInterval(() => setElapsed((n) => n + 1), 1000); setDialog('matching');
  };
  const stop = () => { send({ type: 'stop_matchmaking' }); clearTimer(); setDialog(null); };
  const ordered = users.filter((u) => filter === 'all' || (rank && u.ladder_rung === rank.rung))
    .sort((a, b) => Number(b.id === centralId) - Number(a.id === centralId) || Number(a.presence === 'playing') - Number(b.presence === 'playing'));
  const openPlayers = () => {
    if (tab === 'players') peersRef.current?.focus();
    else { focusPlayers.current = true; setTab('players'); }
  };
  const selectTab = (next: 'games' | 'players', focus = false) => {
    setTab(next);
    if (focus) document.getElementById(`pvp-${next}-tab`)?.focus();
  };
  const modalOpen = !!(invite || outgoing || dialog);
  const closeModal = () => {
    if (invite) setInvite(null);
    else if (outgoing) setOutgoing(null);
    else if (dialog === 'matching') stop();
    else setDialog(null);
  };
  const title = invite ? `${invite.from_name}邀你下一局` : outgoing ? `邀请 ${outgoing.username} 对局`
    : dialog === 'placement' ? '需要先完成定级' : '正在寻找同段位对手';
  if (!isAuthenticated) return <div className="pvp-kiosk pvp-kiosk--guest" data-testid="lobby-guest">
    <header className="pvp-kiosk__bar"><button type="button" onClick={() => navigate('/kiosk/play')}>← 返回对弈</button><h1>在线大厅</h1></header>
    <section><h2>登录后进在线大厅</h2><p>登录后，棋友可以在名单中看到你并邀请你对局。</p><button type="button" onClick={() => navigate('/kiosk/login')}>前往登录</button></section>
  </div>;
  return <div className="pvp-kiosk" data-testid="lobby-page">
    <div className="pvp-kiosk__content" inert={modalOpen}>
      <header className="pvp-kiosk__bar">
        <button type="button" onClick={() => navigate('/kiosk/play')}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 12H5m7-7-7 7 7 7" /></svg>返回对弈</button>
        <h1>在线大厅</h1><span className={`pvp-kiosk__connection${connection === 'connected' ? ' is-connected' : ''}`}>
          {connection === 'connected' ? '已连接' : connection === 'connecting' ? '连接中' : '已断开'}</span>
        <span className="pvp-kiosk__rank"><small>我的段位</small><b>{rankLoaded ? rankError ? '段位读取失败' : rank?.label || '尚未定级' : '读取中'}</b></span>
      </header>
      <section className="pvp-kiosk__start" aria-label="开一局">
        <div className="pvp-kiosk__label">开一局 <em>Start</em></div>
        <div className="pvp-kiosk__start-grid">
          <button type="button" onClick={start} disabled={!rankLoaded || rankError || centralId === null || connection !== 'connected'}>
            <span className="tile"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 13a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM2 20c0-4 3-6 7-6s7 2 7 6M17 5a4 4 0 0 1 0 8m1 1c2.5.7 4 2.6 4 5" /></svg></span>
            <span><strong>快速匹配</strong><small>按当前段位找棋友 · 不计升降段位</small></span><span className="arrow" aria-hidden="true">→</span>
          </button>
          <button type="button" onClick={openPlayers}>
            <span className="tile"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="9" cy="8" r="4" /><path d="M2 20c0-4 3-6 7-6 2 0 4 .7 5 2m5-7v8m-4-4h8" /></svg></span>
            <span><strong>邀请棋友</strong><small>直接邀请任意段位的空闲棋友</small></span><span className="arrow" aria-hidden="true">→</span>
          </button>
        </div>
      </section>
      {rankError && <div role="alert" className="pvp-kiosk__error">段位状态暂时无法读取。<button type="button" onClick={() => void loadRank()}>重试段位</button></div>}
      {(identityError || loadError || connection === 'disconnected' || notice) && <div role="alert" className="pvp-kiosk__error">
        {identityError ? '无法确认中央账号身份，请重试。' : loadError ? '大厅数据读取失败。' : connection === 'disconnected' ? '大厅连接已断开，请稍后重试。' : notice}
        <button type="button" onClick={retryLobby}>重试</button>
      </div>}
      <section className="pvp-kiosk__hall" aria-label="对战大厅">
        <div className="pvp-kiosk__label">对战大厅 <em>Lobby</em></div>
        <div className="pvp-kiosk__list">
          <header className="pvp-kiosk__list-head">
            <div role="tablist" aria-label="大厅内容" className="pvp-kiosk__tabs" onKeyDown={(event) => {
              let next: 'games' | 'players';
              if (event.key === 'Home') next = 'games';
              else if (event.key === 'End') next = 'players';
              else if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') next = tab === 'games' ? 'players' : 'games';
              else return;
              event.preventDefault(); selectTab(next, true);
            }}>
              <button type="button" id="pvp-games-tab" role="tab" aria-selected={tab === 'games'} aria-controls="pvp-list-panel" tabIndex={tab === 'games' ? 0 : -1} onClick={() => selectTab('games')}>进行中对局 <span>{loaded && !loadError ? games.length : '—'}</span></button>
              <button type="button" id="pvp-players-tab" role="tab" aria-selected={tab === 'players'} aria-controls="pvp-list-panel" tabIndex={tab === 'players' ? 0 : -1} onClick={() => selectTab('players')}>在线棋友 <span>{loaded && !loadError ? users.length : '—'}</span></button>
            </div>
            <small>{tab === 'games' ? '点选棋局可观战 · 大厅对局不计升降段位' : '未定级也可邀请任意段位的空闲棋友'}</small>
          </header>
          <div className="pvp-kiosk__list-body" id="pvp-list-panel" role="tabpanel" aria-labelledby={`pvp-${tab}-tab`} ref={peersRef} tabIndex={0}>
            {tab === 'games' ? <>
              {!loaded && <p className="pvp-kiosk__empty">正在读取对局…</p>}
              {loaded && !loadError && !games.length && <p className="pvp-kiosk__empty">当前没有进行中的对局。</p>}
              <div className="pvp-kiosk__grid">{games.map((game) => {
                const mine = centralId !== null && (game.player_b_id === centralId || game.player_w_id === centralId);
                const count = verifiedSpectatorCount(game.spectator_count);
                const viewers = count === undefined ? '观战人数未返回' : `${count} 人观战`;
                return <button key={game.session_id} data-testid="lobby-game" className="pvp-kiosk__game" type="button"
                  aria-label={`${mine ? '返回对局' : '观战'} ${game.player_b} 对 ${game.player_w}，${viewers}`}
                  onClick={() => mine ? navigate(`/kiosk/play/pvp/room/${game.session_id}`, { state: BACK }) : navigate(`/kiosk/play/pvp/watch/${game.session_id}`)}>
                  <span className="pvp-kiosk__room-top"><b><span className="pvp-kiosk__room-number">{game.session_id.slice(0, 4)}</span> 房</b>
                    <span className="pvp-kiosk__tag">分先</span><span className="pvp-kiosk__tag">19 路</span>
                    <span className="pvp-kiosk__viewers"><Eye /><span>{viewers}</span></span>
                  </span>
                  <span className="pvp-kiosk__room-body">
                    <span className="pvp-kiosk__seat"><span className="pvp-kiosk__avatar">{game.player_b.slice(-1)}<Stone color="black" /></span><span className="pvp-kiosk__seat-name"><b>{game.player_b}</b><small>执黑{game.player_b_rank_label ? ` · ${game.player_b_rank_label}` : ''}</small></span></span>
                    <span className="pvp-kiosk__phase"><span className="pvp-kiosk__mini-board" aria-hidden="true"><Stone color="black" /><Stone color="white" /></span><span>{game.move_count} 手</span></span>
                    <span className="pvp-kiosk__seat pvp-kiosk__seat--white"><span className="pvp-kiosk__avatar">{game.player_w.slice(-1)}<Stone color="white" /></span><span className="pvp-kiosk__seat-name"><b>{game.player_w}</b><small>{game.player_w_rank_label ? `${game.player_w_rank_label} · ` : ''}执白</small></span></span>
                  </span>
                </button>;
              })}</div>
              <p className="pvp-kiosk__foot">黑棋在左，白棋在右；自己的对局可返回棋盘。</p>
            </> : <>
              <div className="pvp-kiosk__filters" role="group" aria-label="棋友筛选">
                <button type="button" aria-pressed={filter === 'all'} onClick={() => setFilter('all')}>全部棋友</button>
                <button type="button" aria-pressed={filter === 'same'} disabled={!rank} onClick={() => setFilter('same')}>同段位</button>
                <small>在线 {loaded && !loadError ? users.length : '—'} 人</small>
              </div>
              {!loaded && <p className="pvp-kiosk__empty">正在读取棋友…</p>}
              {loaded && !loadError && !ordered.length && <p className="pvp-kiosk__empty">当前筛选下没有在线棋友。</p>}
              <div className="pvp-kiosk__grid">{ordered.map((person) => {
                const me = centralId !== null && person.id === centralId;
                const busy = person.presence !== 'idle';
                return <div key={person.id} data-testid={`lobby-player-${person.id}`} className="pvp-kiosk__peer">
                  <span className="pvp-kiosk__avatar">{person.username.slice(-1)}</span>
                  <span className="pvp-kiosk__peer-name"><b>{person.username}</b><small>{person.rank_label || '尚未定级'}</small></span>
                  <span className={`pvp-kiosk__peer-state${busy ? ' is-busy' : ''}`}>{busy ? '对局中' : '空闲'}</span>
                  {me ? <span className="pvp-kiosk__self">这是你</span> : <button type="button" disabled={busy || centralId === null || connection !== 'connected'} onClick={() => { inviteSent.current = false; setOutgoing(person); }}>邀请</button>}
                </div>;
              })}</div>
              <p className="pvp-kiosk__foot">空闲棋友可邀请；快速匹配需先完成定级。</p>
            </>}
          </div>
        </div>
      </section>
    </div>
    {modalOpen && <LobbyDialog key={title} title={title} onClose={closeModal}>
      {invite ? <><p>接受后直接开局；这局不计升降段位。</p><div className="actions"><button type="button" onClick={closeModal}>拒绝</button><button type="button" className="main" onClick={() => { send({ type: 'accept_invite', target_id: invite.from_id }); setInvite(null); }}>接受并开局</button></div></>
        : outgoing ? <><p>对方空闲。未定级也可邀请任意段位棋友，本局不计升降段位。</p><div className="fact">对方段位 · {outgoing.rank_label || '尚未定级'}</div><div className="actions"><button type="button" onClick={closeModal}>返回大厅</button><button type="button" className="main" onClick={() => {
          if (inviteSent.current) return;
          inviteSent.current = true;
          if (send({ type: 'invite', target_id: outgoing.id })) setNotice('邀请已发送，等待对方回应。');
          setOutgoing(null);
        }}>发送邀请</button></div></>
          : <><p>{dialog === 'placement' ? '快速匹配按你的升降级段位寻找同水平对手。请先在「升降级对弈」完成 5 局定级赛。你仍可直接邀请空闲棋友。' : '先寻找同段位真人，稍后由同段位棋手接局；匹配成功后直接进入棋盘。'}</p>
            <div className="fact"><span>{dialog === 'placement' ? '当前段位' : `${rank?.label} · 不计升降段位`}</span><b>{dialog === 'placement' ? '尚未定级' : `已等 ${elapsed} 秒`}</b></div>
            {dialog === 'matching' && <div className="wait-line" />}
            <div className="actions">{dialog === 'placement' ? <><button type="button" onClick={closeModal}>稍后再说</button><button type="button" className="main" onClick={() => navigate('/kiosk/play/ai/setup/ranked')}>去升降级对弈</button></> : <button type="button" onClick={stop}>取消匹配</button>}</div>
          </>}
    </LobbyDialog>}
  </div>;
}
