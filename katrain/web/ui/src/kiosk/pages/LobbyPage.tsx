import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getAiLadderStatus } from '../../features/aiLadder/api';
import { websocketUrl } from '../../utils/websocketUrl';
import { isStrictBoxKiosk } from '../shell/boxUrls';
import './LobbyPage.css';

type Person = { id: number; username: string; ladder_rung: number | null; rank_label: string | null; presence: 'idle' | 'playing' };
type Game = { session_id: string; player_b: string; player_w: string; player_b_id?: number; player_w_id?: number; player_b_rank_label?: string | null; player_w_rank_label?: string | null; move_count: number };
const isPerson = (v: unknown): v is Person => !!v && typeof v === 'object' && typeof (v as Person).id === 'number' && typeof (v as Person).username === 'string';
const isGame = (v: unknown): v is Game => !!v && typeof v === 'object' && typeof (v as Game).session_id === 'string' && typeof (v as Game).player_b === 'string' && typeof (v as Game).player_w === 'string';
const BACK = { backTo: '/kiosk/play/pvp/lobby' };
export default function LobbyPage() {
  const navigate = useNavigate();
  const { user, token, isAuthenticated } = useAuth();
  const [centralId, setCentralId] = useState<number | null>(isStrictBoxKiosk ? null : user?.id ?? null);
  const [identityError, setIdentityError] = useState(false);
  const [users, setUsers] = useState<Person[]>([]);
  const [games, setGames] = useState<Game[]>([]);
  const [rank, setRank] = useState<{ rung: number; label: string } | null>(null);
  const [rankLoaded, setRankLoaded] = useState(false);
  const [rankError, setRankError] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [filter, setFilter] = useState<'all' | 'same'>('all');
  const [dialog, setDialog] = useState<'placement' | 'matching' | null>(null);
  const [invite, setInvite] = useState<{ from_id: number; from_name: string } | null>(null);
  const [notice, setNotice] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const socket = useRef<WebSocket | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const rankRequest = useRef(0);
  const peersRef = useRef<HTMLDivElement>(null);
  const clearTimer = () => { if (timer.current) clearInterval(timer.current); timer.current = null; };
  const fetchLists = useCallback(async () => {
    if (!isAuthenticated) return;
    try {
      const [u, g] = await Promise.all([
        fetch('/api/v1/users/online', { headers: token ? { Authorization: `Bearer ${token}` } : undefined }),
        fetch('/api/v1/games/active/multiplayer', { headers: token ? { Authorization: `Bearer ${token}` } : undefined }),
      ]);
      if (!u.ok || !g.ok) throw new Error();
      const [uRows, gRows]: unknown[] = await Promise.all([u.json(), g.json()]);
      setUsers(Array.isArray(uRows) ? uRows.filter(isPerson) : []);
      setGames(Array.isArray(gRows) ? gRows.filter(isGame) : []);
      setLoadError(false);
    } catch { setLoadError(true); }
    finally { setLoaded(true); }
  }, [isAuthenticated, token]);
  useEffect(() => {
    if (!isAuthenticated) return;
    if (!isStrictBoxKiosk) { setCentralId(user?.id ?? null); return; }
    let cancelled = false;
    fetch('/api/pvp/identity', { headers: token ? { Authorization: `Bearer ${token}` } : undefined, credentials: 'same-origin' })
      .then((r) => { if (!r.ok) throw new Error(); return r.json(); })
      .then((data: unknown) => {
        const id = data && typeof data === 'object' ? (data as Record<string, unknown>).user_id : null;
        if (typeof id !== 'number') throw new Error();
        if (!cancelled) { setCentralId(id); setIdentityError(false); }
      }).catch(() => { if (!cancelled) { setCentralId(null); setIdentityError(true); } });
    return () => { cancelled = true; };
  }, [isAuthenticated, token, user?.id]);
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
  useEffect(() => { void loadRank(); }, [loadRank]);
  useEffect(() => {
    if (!isAuthenticated) return;
    void fetchLists();
    const refresh = setInterval(() => { void fetchLists(); }, 10000);
    const ws = new WebSocket(websocketUrl('/ws/lobby', token));
    socket.current = ws;
    ws.onopen = () => setConnection('connected');
    ws.onclose = () => { setConnection('disconnected'); setDialog((d) => d === 'matching' ? null : d); clearTimer(); };
    ws.onerror = () => setConnection('disconnected');
    ws.onmessage = (event) => {
      let data: Record<string, unknown>;
      try { data = JSON.parse(event.data); } catch { return; }
      if (data.type === 'match_found' && typeof data.session_id === 'string') {
        clearTimer(); setDialog(null); navigate(`/kiosk/play/pvp/room/${data.session_id}`, { state: BACK });
      } else if (data.type === 'lobby_update') void fetchLists();
      else if (data.type === 'invitation') setInvite({ from_id: Number(data.from_id), from_name: String(data.from_name) });
      else if (data.type === 'error') {
        clearTimer();
        if (data.code === 'PLACEMENT_REQUIRED') setDialog('placement');
        else { setDialog(null); setNotice(data.code === 'INVITE_NOT_PENDING' ? '邀请已过期，请对方重新邀请。' : String(data.message || '操作失败，请重试。')); }
      } else if (data.type === 'info') setNotice(String(data.message || ''));
    };
    return () => { ws.close(); clearInterval(refresh); clearTimer(); };
  }, [isAuthenticated, token, fetchLists, navigate]);
  const send = (message: Record<string, unknown>) => {
    if (socket.current?.readyState !== WebSocket.OPEN) { setNotice('大厅连接已断开，请稍后重试。'); return false; }
    socket.current.send(JSON.stringify(message)); return true;
  };
  const start = () => {
    if (!rankLoaded || rankError) return;
    if (!rank) { setDialog('placement'); return; }
    if (!send({ type: 'start_matchmaking' })) return;
    clearTimer(); setElapsed(0); timer.current = setInterval(() => setElapsed((n) => n + 1), 1000); setDialog('matching');
  };
  const stop = () => { send({ type: 'stop_matchmaking' }); clearTimer(); setDialog(null); };
  const ordered = users.filter((u) => filter === 'all' || (rank && u.ladder_rung === rank.rung))
    .sort((a, b) => Number(b.id === centralId) - Number(a.id === centralId) || Number(a.presence === 'playing') - Number(b.presence === 'playing'));
  if (!isAuthenticated) return <div className="pvp-kiosk pvp-kiosk--guest" data-testid="lobby-guest"><div className="pvp-kiosk__bar"><button onClick={() => navigate('/kiosk/play')}>← 返回对弈</button><strong>在线大厅</strong></div><section><h2>登录后进在线大厅</h2><p>登录后，棋友可以在名单中看到你并邀请你对局。</p><button onClick={() => navigate('/kiosk/login')}>前往登录</button></section></div>;
  return <div className="pvp-kiosk" data-testid="lobby-page">
    <div className="pvp-kiosk__bar"><button type="button" onClick={() => navigate('/kiosk/play')}>← 返回对弈</button><strong>在线大厅</strong><small>自有对战 · 与同段位棋友对局</small><span>我的段位 <b>{rankLoaded ? rankError ? '段位读取失败' : rank?.label || '尚未定级' : '读取中'}</b></span></div>
    <section className="pvp-kiosk__start"><div className="pvp-kiosk__label">开一局 <em>Start</em></div><div className="pvp-kiosk__start-grid"><button className="primary" type="button" onClick={start} disabled={!rankLoaded || rankError || connection !== 'connected'}><span className="tile">棋</span><span><strong>快速匹配</strong><small>按当前段位找对手 · 本大厅对局不计升降段位</small></span><span className="arr">开始匹配 →</span></button><button type="button" onClick={() => peersRef.current?.focus()}><span className="tile">友</span><span><strong>邀请棋友</strong><small>从右侧名单选择空闲棋手</small></span><span className="arrow">→</span></button></div></section>
    {rankError && <div role="alert" className="pvp-kiosk__error">段位状态暂时无法读取。<button type="button" onClick={() => void loadRank()}>重试段位</button></div>}
    {(identityError || loadError || connection === 'disconnected' || notice) && <div role="alert" className="pvp-kiosk__error">{identityError ? '无法确认中央账号身份，请重试。' : loadError ? '大厅数据读取失败。' : connection === 'disconnected' ? '大厅连接已断开，请稍后重试。' : notice}<button type="button" onClick={() => { setNotice(''); void fetchLists(); }}>重试</button></div>}
    <div className="pvp-kiosk__hall"><section className="pvp-kiosk__col" aria-label="进行中的对局"><header><div className="pvp-kiosk__label">进行中的对局 <em>In play</em></div><span>{games.length} 局</span></header><div className="pvp-kiosk__list">{!loaded && <p>正在读取对局…</p>}{loaded && !games.length && <p>当前没有进行中的对局。</p>}{games.map((g) => { const mine = centralId !== null && (g.player_b_id === centralId || g.player_w_id === centralId); const Cell = mine ? 'button' : 'article'; return <Cell key={g.session_id} data-testid="lobby-game" className="pvp-kiosk__game" {...(mine ? { type: 'button' as const, onClick: () => navigate(`/kiosk/play/pvp/room/${g.session_id}`, { state: BACK }) } : {})}><span className="meta"><span>{g.session_id.slice(0, 4)} 房</span><span>第 {g.move_count} 手</span><span>19 路 · 对局中</span></span><span className="pair"><span className="player"><b>{g.player_b}</b><small>● 执黑{g.player_b_rank_label ? ` · ${g.player_b_rank_label}` : ''}</small></span><span className="vs">对</span><span className="player"><b>{g.player_w}</b><small>{g.player_w_rank_label ? `${g.player_w_rank_label} · ` : ''}执白 ○</small></span></span></Cell>; })}</div><footer>只列真实进行中的对局；自己的对局可返回棋盘。</footer></section>
    <section className="pvp-kiosk__col" aria-label="在线棋友"><header><div className="pvp-kiosk__label">在线棋友 <em>Players</em></div><div role="tablist" className="tabs"><button role="tab" aria-selected={filter === 'all'} onClick={() => setFilter('all')}>全部</button><button role="tab" aria-selected={filter === 'same'} disabled={!rank} onClick={() => setFilter('same')}>同段位</button></div><span>在线 {users.length} 人</span></header><div className="pvp-kiosk__list" ref={peersRef} tabIndex={-1}>{!loaded && <p>正在读取棋友…</p>}{loaded && !ordered.length && <p>当前筛选下没有在线棋友。</p>}{ordered.map((u) => { const me = centralId !== null && u.id === centralId; const busy = u.presence === 'playing'; return <div key={u.id} data-testid={`lobby-player-${u.id}`} className={`pvp-kiosk__peer ${me ? 'me' : ''}`}><span className="avatar">{u.username.slice(0, 1)}</span><span className="name"><b>{u.username}</b><small>{u.rank_label || '尚未定级'}</small></span><span className={`state ${busy ? 'busy' : ''}`}>{busy ? '对局中' : '空闲'}</span>{me ? <span className="self">这是你</span> : <button type="button" disabled={busy || connection !== 'connected'} onClick={() => send({ type: 'invite', target_id: u.id })}>邀请</button>}</div>; })}</div><footer>空闲棋手可邀请；同段位筛选按已定级段位计算。</footer></section></div>
    {dialog && <div className="pvp-kiosk__layer"><section role="dialog" aria-modal="true"><h2>{dialog === 'placement' ? '需要先完成定级' : '正在寻找同段位对手'}</h2><p>{dialog === 'placement' ? '快速匹配按你的升降级段位寻找同水平对手。请先在「升降级对弈」完成 5 局定级赛。' : '先寻找同段位真人，稍后由同段位棋手接局；匹配成功后直接进入棋盘。'}</p><div className="fact"><span>{dialog === 'placement' ? '当前段位' : `${rank?.label} · 不计升降段位`}</span><b>{dialog === 'placement' ? '尚未定级' : `已等 ${elapsed} 秒`}</b></div>{dialog === 'matching' && <div className="wait-line" />}<div className="actions">{dialog === 'placement' ? <><button onClick={() => setDialog(null)}>稍后再说</button><button className="main" onClick={() => navigate('/kiosk/play/ai/setup/ranked')}>去升降级对弈</button></> : <button onClick={stop}>取消匹配</button>}</div></section></div>}
    {invite && <div className="pvp-kiosk__layer"><section role="dialog" aria-modal="true"><h2>{invite.from_name}邀你下一局</h2><p>接受后直接开局；这局不计升降段位。</p><div className="actions"><button onClick={() => setInvite(null)}>拒绝</button><button className="main" onClick={() => { send({ type: 'accept_invite', target_id: invite.from_id }); setInvite(null); }}>接受并开局</button></div></section></div>}
  </div>;
}
