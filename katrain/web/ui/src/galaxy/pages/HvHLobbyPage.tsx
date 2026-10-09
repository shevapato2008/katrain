import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { getAiLadderStatus } from '../../features/aiLadder/api';
import { websocketUrl } from '../../utils/websocketUrl';
import './HvHLobbyPage.css';

type OnlineUser = { id: number; username: string; ladder_rung: number | null; rank_label: string | null; presence: 'idle' | 'playing' };
type ActiveGame = { session_id: string; player_b: string; player_w: string; player_b_id?: number; player_w_id?: number; player_b_rank_label?: string | null; player_w_rank_label?: string | null; move_count: number };
type Dialog = 'placement' | 'matching' | null;
const isUser = (value: unknown): value is OnlineUser => {
  if (!value || typeof value !== 'object') return false;
  const u = value as Partial<OnlineUser>;
  return typeof u.id === 'number' && typeof u.username === 'string';
};
const isGame = (value: unknown): value is ActiveGame => {
  if (!value || typeof value !== 'object') return false;
  const g = value as Partial<ActiveGame>;
  return typeof g.session_id === 'string' && typeof g.player_b === 'string' && typeof g.player_w === 'string';
};

export default function HvHLobbyPage() {
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const [users, setUsers] = useState<OnlineUser[]>([]);
  const [games, setGames] = useState<ActiveGame[]>([]);
  const [following, setFollowing] = useState<number[]>([]);
  const [rank, setRank] = useState<{ rung: number; label: string } | null>(null);
  const [rankLoaded, setRankLoaded] = useState(false);
  const [rankError, setRankError] = useState(false);
  const [filter, setFilter] = useState<'all' | 'same' | 'follow'>('all');
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState('');
  const [connection, setConnection] = useState<'connecting' | 'connected' | 'disconnected'>('connecting');
  const [dialog, setDialog] = useState<Dialog>(null);
  const [elapsed, setElapsed] = useState(0);
  const [invitation, setInvitation] = useState<{ from_id: number; from_name: string } | null>(null);
  const [notice, setNotice] = useState('');
  const socket = useRef<WebSocket | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const rankRequest = useRef(0);
  const clearTimer = () => { if (timer.current) clearInterval(timer.current); timer.current = null; };
  const fetchLists = useCallback(async () => {
    if (!token) return;
    try {
      const [u, g] = await Promise.all([
        fetch('/api/v1/users/online', { headers: { Authorization: `Bearer ${token}` } }),
        fetch('/api/v1/games/active/multiplayer', { headers: { Authorization: `Bearer ${token}` } }),
      ]);
      if (!u.ok || !g.ok) throw new Error('大厅暂时无法连接，请稍后重试。');
      const [uRows, gRows]: unknown[] = await Promise.all([u.json(), g.json()]);
      setUsers(Array.isArray(uRows) ? uRows.filter(isUser) : []);
      setGames(Array.isArray(gRows) ? gRows.filter(isGame) : []);
      setError('');
    } catch {
      setUsers([]);
      setGames([]);
      setError('大厅暂时无法连接，请稍后重试。');
    }
    finally { setLoaded(true); }
  }, [token]);
  const loadRank = useCallback(async () => {
    if (!token) return;
    const request = ++rankRequest.current;
    setRankLoaded(false);
    setRankError(false);
    try {
      const status = await getAiLadderStatus(token);
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
  }, [token]);
  useEffect(() => { void loadRank(); }, [loadRank]);
  useEffect(() => {
    if (!token) return;
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
        clearTimer(); setDialog(null); navigate(`/galaxy/play/human/room/${data.session_id}`);
      } else if (data.type === 'lobby_update') void fetchLists();
      else if (data.type === 'invitation') setInvitation({ from_id: Number(data.from_id), from_name: String(data.from_name) });
      else if (data.type === 'error') {
        if (data.code === 'PLACEMENT_REQUIRED') setDialog('placement');
        else { setDialog(null); setNotice(data.code === 'INVITE_NOT_PENDING' ? '邀请已过期，请对方重新邀请。' : String(data.message || '操作失败，请重试。')); }
        clearTimer();
      } else if (data.type === 'info') setNotice(String(data.message || ''));
    };
    return () => { ws.close(); clearInterval(refresh); clearTimer(); };
  }, [token, fetchLists, navigate]);
  useEffect(() => {
    if (!token) return;
    fetch('/api/v1/users/following', { headers: { Authorization: `Bearer ${token}` } }).then((r) => r.ok ? r.json() : []).then((rows: unknown) => {
      setFollowing(Array.isArray(rows) ? rows.map((row) => Number(row.id)).filter(Number.isFinite) : []);
    }).catch(() => setFollowing([]));
  }, [token]);
  const send = (message: Record<string, unknown>) => {
    if (socket.current?.readyState !== WebSocket.OPEN) { setNotice('大厅连接已断开，请刷新后重试。'); return false; }
    socket.current.send(JSON.stringify(message)); return true;
  };
  const start = () => {
    if (!rankLoaded || rankError) return;
    if (!rank) { setDialog('placement'); return; }
    if (!send({ type: 'start_matchmaking' })) return;
    setElapsed(0); clearTimer(); timer.current = setInterval(() => setElapsed((n) => n + 1), 1000);
    setDialog('matching');
  };
  const stop = () => { send({ type: 'stop_matchmaking' }); clearTimer(); setDialog(null); };
  const roster = users.filter((u) => filter === 'all' || (filter === 'same' ? rank && u.ladder_rung === rank.rung : following.includes(u.id)));
  const ordered = [...roster].sort((a, b) => Number(b.id === user?.id) - Number(a.id === user?.id) || Number(a.presence === 'playing') - Number(b.presence === 'playing'));
  return <main className="pvp-galaxy">
    <div className="pvp-galaxy__heading"><div><h1><button type="button" aria-label="返回对局" onClick={() => navigate('/galaxy/play')}>←</button>对战大厅</h1><p>选择空闲棋友，或一键匹配同段位对手。所有大厅对局均不计升降段位。</p></div><div className="pvp-galaxy__identity"><span className="dot" />{rankLoaded ? rankError ? '段位读取失败' : rank ? '已定级' : '未定级' : '读取段位中'} <b>{rankError ? '请重试' : rank?.label || (rankLoaded ? '先去升降级对弈' : '…')}</b></div></div>
    <section className="pvp-galaxy__action" aria-label="快速匹配"><span className="emblem">棋</span><div><strong>来下一局</strong><small>优先寻找同段位真人；等待后由同段位棋手接局</small></div><button type="button" onClick={start} disabled={!rankLoaded || rankError || connection !== 'connected'}>快速匹配 →</button></section>
    {rankError && <p role="alert" className="pvp-galaxy__alert">段位状态暂时无法读取。<button type="button" onClick={() => void loadRank()}>重试段位</button></p>}
    {connection === 'disconnected' && <p role="alert" className="pvp-galaxy__alert">大厅连接已断开，请刷新后重试。</p>}
    {error && <p role="alert" className="pvp-galaxy__alert">{error} <button type="button" onClick={() => void fetchLists()}>重试</button></p>}
    {notice && <p role="status" className="pvp-galaxy__alert">{notice}<button type="button" onClick={() => setNotice('')}>关闭</button></p>}
    <div className="pvp-galaxy__layout">
      <section className="pvp-galaxy__panel" aria-label="进行中的对局"><header><h2>进行中的对局</h2><em>In play</em><span>{error ? '—' : games.length} 局正在进行</span></header><div className="pvp-galaxy__body">{!loaded && <p>正在读取对局…</p>}{loaded && !error && !games.length && <p>当前没有进行中的对局。</p>}{games.map((g) => { const mine = g.player_b_id === user?.id || g.player_w_id === user?.id; return <article className="pvp-galaxy__game" data-testid="lobby-game" key={g.session_id}><div className="meta"><b>{g.session_id.slice(0, 4)} 房</b><span>分先 · 19 路</span><span>第 {g.move_count} 手</span></div><div className="pair"><div className="side"><span className="portrait">{g.player_b.slice(0, 1)}</span><div><b>{g.player_b}</b><small>执黑{g.player_b_rank_label ? ` · ${g.player_b_rank_label}` : ''}</small></div></div><span className="versus">对</span><div className="side white"><div><b>{g.player_w}</b><small>{g.player_w_rank_label ? `${g.player_w_rank_label} · ` : ''}执白</small></div><span className="portrait">{g.player_w.slice(0, 1)}</span></div></div>{mine && <button type="button" onClick={() => navigate(`/galaxy/play/human/room/${g.session_id}`)}>返回棋盘 →</button>}</article>; })}<p className="tail">只列真实进行中的对局；自己的对局可返回棋盘。</p></div></section>
      <section className="pvp-galaxy__panel" aria-label="在线棋友"><header><h2>在线棋友</h2><em>Players</em><span>{error ? '—' : users.length} 人在线</span></header><div className="pvp-galaxy__tabs" role="tablist"><button role="tab" aria-selected={filter === 'all'} onClick={() => setFilter('all')}>全部棋友</button><button role="tab" aria-selected={filter === 'same'} disabled={!rank} onClick={() => setFilter('same')}>同段位</button><button role="tab" aria-selected={filter === 'follow'} onClick={() => setFilter('follow')}>我的关注</button></div><div className="pvp-galaxy__peers">{!loaded && <p>正在读取棋友…</p>}{loaded && !error && !ordered.length && <p>当前筛选下没有在线棋友。</p>}{ordered.map((u) => { const me = u.id === user?.id; const busy = u.presence === 'playing'; return <div className={`peer ${me ? 'self' : ''}`} data-testid={`lobby-player-${u.id}`} key={u.id}><span className="portrait">{u.username.slice(0, 1)}</span><span className="name"><b>{u.username}</b><small>{u.rank_label || '尚未定级'}</small></span><span className={`state ${busy ? 'busy' : ''}`}>{busy ? '对局中' : '空闲'}</span>{me ? <span className="self-tag">这是你</span> : <button type="button" disabled={busy || connection !== 'connected'} onClick={() => send({ type: 'invite', target_id: u.id })}>邀请</button>}</div>; })}</div><p className="pvp-galaxy__tail">空闲棋手可邀请；同段位筛选按已定级段位计算。</p></section>
    </div>
    {dialog && <div className="pvp-galaxy__layer"><section className="pvp-galaxy__dialog" role="dialog" aria-modal="true"><h2>{dialog === 'placement' ? '完成定级后再来匹配' : '正在寻找同段位对手'}</h2><p>{dialog === 'placement' ? '大厅按「升降级对弈」的段位寻找同水平对手。请先完成 5 局定级赛，再回到这里匹配。' : '先寻找同段位真人，稍后由同段位棋手接局；成功后直接开局。'}</p><div className="detail"><span>{dialog === 'placement' ? '当前段位' : `${rank?.label} · 不计升降段位`}</span><b>{dialog === 'placement' ? '尚未定级' : `已等 ${elapsed} 秒`}</b></div>{dialog === 'matching' && <div className="progress" />}<div className="actions">{dialog === 'placement' ? <><button onClick={() => setDialog(null)}>返回大厅</button><button className="main" onClick={() => navigate('/galaxy/play/ai?mode=rated')}>去升降级对弈</button></> : <button onClick={stop}>取消匹配</button>}</div></section></div>}
    {invitation && <div className="pvp-galaxy__layer"><section className="pvp-galaxy__dialog" role="dialog" aria-modal="true"><h2>{invitation.from_name} 邀你下一局</h2><p>接受后直接开局；这局不计升降段位。</p><div className="actions"><button onClick={() => setInvitation(null)}>返回大厅</button><button className="main" onClick={() => { send({ type: 'accept_invite', target_id: invitation.from_id }); setInvitation(null); }}>接受邀请</button></div></section></div>}
  </main>;
}
