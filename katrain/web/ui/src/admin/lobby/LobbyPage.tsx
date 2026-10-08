import { useEffect, useState } from 'react';
import { AdminApiError, type createAdminApi } from '../api/client';
import type { LobbyConfig, LobbyOverview, ParticipantPage, ParticipantQuery } from './types';
import './LobbyPage.css';

type Api = ReturnType<typeof createAdminApi>;
type Group = 'all' | 'kyu' | 'dan' | 'pro';
const groups: { id: Group; label: string }[] = [
  { id: 'all', label: '全部 29 档' }, { id: 'kyu', label: '级位' },
  { id: 'dan', label: '段位' }, { id: 'pro', label: '职业及以上' },
];
const groupOf = (name: string): Group => name.includes('级') ? 'kyu' : name.includes('段') ? 'dan' : 'pro';
const labelOf = (state: string) => state === 'idle' ? '空闲' : state === 'playing' ? '对局中' : '离线';
const copyConfig = (config: LobbyConfig): LobbyConfig => ({ ...config, idle_targets: { ...config.idle_targets } });

export default function LobbyPage({ api, onUnauthorized }: { api: Api; onUnauthorized: () => void }) {
  const [overview, setOverview] = useState<LobbyOverview | null>(null);
  const [draft, setDraft] = useState<LobbyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [conflict, setConflict] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reload, setReload] = useState(0);
  const [group, setGroup] = useState<Group>('all');
  const [query, setQuery] = useState<ParticipantQuery>({ page: 1, page_size: 30, kind: 'all', presence: 'online', q: '' });
  const [people, setPeople] = useState<ParticipantPage | null>(null);
  const [peopleError, setPeopleError] = useState('');
  const [onlineHumans, setOnlineHumans] = useState<number | null>(null);
  const [clock, setClock] = useState(Date.now());

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 5_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    api.pvpLobby(controller.signal).then((value) => {
      if (controller.signal.aborted) return;
      setOverview(value);
      setDraft((old) => old && overview && (conflict || JSON.stringify(old) !== JSON.stringify(overview.config)) ? old : copyConfig(value.config));
      setConflict(false);
    }).catch((cause) => {
      if (controller.signal.aborted) return;
      if (cause instanceof AdminApiError && cause.status === 401) onUnauthorized();
      else setError(cause instanceof Error ? cause.message : '读取大厅设置失败。');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  // Reload is an explicit action; the API instance belongs to the app shell.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload]);

  useEffect(() => {
    const controller = new AbortController();
    setPeopleError('');
    api.pvpParticipants(query, controller.signal).then((value) => { if (!controller.signal.aborted) setPeople(value); })
      .catch((cause) => { if (!controller.signal.aborted) { if (cause instanceof AdminApiError && cause.status === 401) onUnauthorized(); else setPeopleError(cause instanceof Error ? cause.message : '读取参与者失败。'); } });
    return () => controller.abort();
  // onUnauthorized and api are stable for this mounted page.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    const controller = new AbortController();
    api.pvpParticipants({ page: 1, page_size: 1, kind: 'human', presence: 'online', q: '' }, controller.signal)
      .then((value) => { if (!controller.signal.aborted) setOnlineHumans(value.total); })
      .catch(() => { if (!controller.signal.aborted) setOnlineHumans(null); });
    return () => controller.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reload]);

  const runtime = overview?.runtime ?? { reported_at: null, applied_config_revision: null, stale: true, active_bot_games: null, engine_errors: null, rungs: [] };
  const stale = runtime.stale || !runtime.reported_at || clock - Date.parse(runtime.reported_at) > 30_000;
  const applied = runtime?.applied_config_revision === overview?.config_revision;
  const dirty = !!(draft && overview && JSON.stringify(draft) !== JSON.stringify(overview.config));
  const targetTotal = Object.values(draft?.idle_targets ?? {}).reduce((sum, n) => sum + n, 0);
  const idleTotal = runtime?.rungs.reduce((sum, row) => sum + (row.idle_now ?? 0), 0) ?? null;
  const status = stale ? '运行状态已过期' : !applied ? '设置等待应用' : (runtime?.engine_errors ?? 0) > 0 ? '引擎出现异常' : '服务端投放正常';

  function patchDraft(patch: Partial<LobbyConfig>) { setDraft((current) => current ? { ...current, ...patch } : current); setMessage(''); }
  function adjustRung(rung: number, delta: number) {
    if (!draft) return;
    const current = draft.idle_targets[String(rung)];
    patchDraft({ idle_targets: { ...draft.idle_targets, [rung]: Math.min(20, Math.max(1, current + delta)) } });
  }
  async function save() {
    if (!overview || !draft || stale || !dirty || conflict) return;
    setSaving(true); setError(''); setMessage('');
    try {
      const saved = await api.savePvpLobby({ expected_revision: overview.config_revision, config: draft });
      setOverview(saved); setDraft(copyConfig(saved.config));
      setMessage(saved.runtime.applied_config_revision === saved.config_revision ? '设置已保存并应用。' : '设置已保存，等待服务端应用。');
    } catch (cause) {
      if (cause instanceof AdminApiError && cause.status === 409) { setConflict(true); setError('服务器设置已变化。请读取服务器设置并核对草稿。'); }
      else if (cause instanceof AdminApiError && cause.status === 401) onUnauthorized();
      else setError(cause instanceof Error ? cause.message : '保存失败，请重试。');
    } finally { setSaving(false); }
  }
  function changeFilter(patch: Partial<ParticipantQuery>) { setQuery((old) => ({ ...old, ...patch, page: 1 })); }

  return <main className="admin-lobby" aria-label="对战大厅管理">
    <header className="admin-lobby-head"><div><h1>对战大厅</h1><p>按段位维持空闲棋手，控制机器人互战数量，并查看大厅参与者。</p></div><span className={`admin-lobby-status ${stale ? 'stale' : !applied || (runtime.engine_errors ?? 0) > 0 ? 'pending' : ''}`}>{status}</span></header>
    {loading && !overview ? <div className="admin-lobby-load" role="status">正在读取大厅设置…</div> : error && !overview ? <div className="admin-lobby-load" role="alert">{error}<button onClick={() => setReload((n) => n + 1)}>重试</button></div> : overview && draft && <>
      <section className="admin-lobby-toolbar" aria-label="大厅投放设置"><label className="admin-lobby-switch"><input type="checkbox" checked={draft.enabled} onChange={(e) => patchDraft({ enabled: e.target.checked })} /><span><strong>机器人投放</strong><small>关闭后停止补充与新互战</small></span></label><span className="admin-lobby-divider" /><div className="admin-lobby-global"><span><strong>互战上限</strong><small>全大厅同时进行</small></span><div className="admin-lobby-stepper"><button aria-label="减少互战上限" disabled={draft.bot_game_limit <= 0} onClick={() => patchDraft({ bot_game_limit: draft.bot_game_limit - 1 })}>−</button><output>{draft.bot_game_limit}</output><button aria-label="增加互战上限" disabled={draft.bot_game_limit >= 6} onClick={() => patchDraft({ bot_game_limit: draft.bot_game_limit + 1 })}>+</button></div><small>盘</small></div><span className="admin-lobby-spacer" />{dirty && <span className="admin-lobby-unsaved">有未保存的改动</span>}<button className="admin-lobby-save" disabled={!dirty || stale || conflict || saving} onClick={save}>{saving ? '保存中…' : '保存设置'}</button></section>
      <p className="admin-lobby-hint"><strong>数量含义：</strong>每档填写希望保持的空闲机器人数量；已进入对局的机器人另计。机器人每 5–30 秒落一手；以下覆盖目前可用的 {runtime.rungs.length} 档棋力。{stale && <span> 当前数量暂不可用。<button onClick={() => setReload((n) => n + 1)}>刷新状态</button></span>}</p>
      <div className="admin-lobby-workspace"><section className="admin-lobby-box" aria-label="逐段位机器人设置"><div className="admin-lobby-boxhead"><h2>逐段位投放</h2><span>{runtime.rungs.length} 档 · 目标空闲 {targetTotal} 人</span></div><div className="admin-lobby-groups" role="tablist" aria-label="段位筛选">{groups.map((item) => <button key={item.id} role="tab" aria-selected={group === item.id} onClick={() => setGroup(item.id)}>{item.label}</button>)}</div><div className="admin-lobby-rankhead"><span>棋力档位</span><span>空闲目标</span><span>当前空闲 / 对局中</span><span>投放状态</span></div><div className="admin-lobby-ranks">{runtime.rungs.filter((row) => group === 'all' || groupOf(row.rank_label) === group).map((row) => { const target = draft.idle_targets[String(row.rung)]; const countKnown = !stale && row.idle_now !== null && row.playing_now !== null; const health = !countKnown ? '状态未知' : row.idle_now! < target ? `待补 ${target - row.idle_now!}` : row.idle_now! > target ? `多出 ${row.idle_now! - target}` : '目标已达成'; return <div className="admin-lobby-rankrow" role="row" key={row.rung}><span className="admin-lobby-rankname"><b>{row.rank_label}</b><small>{groups.find((g) => g.id === groupOf(row.rank_label))?.label}</small></span><span className="admin-lobby-stepper"><button aria-label={`减少 ${row.rank_label} 空闲目标`} disabled={target <= 1} onClick={() => adjustRung(row.rung, -1)}>−</button><output>{target}</output><button aria-label={`增加 ${row.rank_label} 空闲目标`} disabled={target >= 20} onClick={() => adjustRung(row.rung, 1)}>+</button></span><span>{countKnown ? `${row.idle_now} 空闲 / ${row.playing_now} 对局中` : '—'}</span><span className={!countKnown ? 'admin-lobby-unknown' : health.startsWith('待补') ? 'admin-lobby-low' : 'admin-lobby-ok'}>{health}</span></div>; })}</div><div className="admin-lobby-boxfoot"><span>每档至少 1 人，最多 20 人。</span><span>当前配置 <b>{targetTotal} 人</b></span></div></section>
      <div className="admin-lobby-right"><section className="admin-lobby-box" aria-label="当前大厅"><div className="admin-lobby-boxhead"><h2>当前大厅</h2><span>{runtime.reported_at ? `上报 ${new Date(runtime.reported_at).toLocaleTimeString('zh-CN')}` : '尚未上报'}</span></div><div className="admin-lobby-metrics"><div><small>空闲机器人</small><strong>{stale ? '—' : idleTotal}</strong></div><div><small>机器人互战</small><strong>{stale ? '—' : runtime.active_bot_games} / {draft.bot_game_limit}</strong></div><div><small>在线真人</small><strong>{stale ? '—' : onlineHumans ?? '—'}</strong></div></div><p>{stale ? '运行快照缺失或已过期；当前数量暂不可用。' : !applied ? `配置第 ${overview.config_revision} 版已保存，服务端仍应用第 ${runtime.applied_config_revision ?? '—'} 版。` : `引擎异常 ${runtime.engine_errors ?? '—'} 次；各段位轮流安排同段位互战。`}</p></section>
      <section className="admin-lobby-box" aria-label="参与者名单"><div className="admin-lobby-boxhead"><h2>参与者</h2><span>真人与机器人在后台区分</span></div><div className="admin-lobby-rosterfilters"><select aria-label="在线状态" value={query.presence} onChange={(e) => changeFilter({ presence: e.target.value as ParticipantQuery['presence'] })}><option value="online">当前在线</option><option value="all">全部账号</option><option value="idle">空闲</option><option value="playing">对局中</option><option value="offline">离线</option></select><select aria-label="身份类型" value={query.kind} onChange={(e) => changeFilter({ kind: e.target.value as ParticipantQuery['kind'] })}><option value="all">全部身份</option><option value="human">真人</option><option value="bot">机器人</option></select><input aria-label="搜索昵称" type="search" placeholder="搜索昵称" value={query.q} onChange={(e) => changeFilter({ q: e.target.value })} /></div><div className="admin-lobby-rosterhead"><span>昵称</span><span>类型</span><span>段位</span><span>状态</span></div><div className="admin-lobby-roster">{peopleError ? <p role="alert">{peopleError}<button onClick={() => setQuery({ ...query })}>重试</button></p> : !people ? <p>正在读取参与者…</p> : people.items.length === 0 ? <p>没有符合筛选条件的参与者</p> : people.items.map((person) => <div className="admin-lobby-person" key={`${person.kind}-${person.id}`}><b title={person.username}>{person.username}</b><span className={`admin-lobby-kind ${person.kind}`}>{person.kind === 'bot' ? '机器人' : '真人'}</span><span>{person.rank_label ?? '—'}</span><span>{labelOf(person.presence)}</span></div>)}</div><div className="admin-lobby-rosterfoot"><span>共 {people?.total ?? '—'} 人 · 第 {query.page} 页</span><div><button aria-label="上一页" disabled={query.page <= 1} onClick={() => setQuery({ ...query, page: query.page - 1 })}>上一页</button><button aria-label="下一页" disabled={!people || query.page * people.page_size >= people.total} onClick={() => setQuery({ ...query, page: query.page + 1 })}>下一页</button></div></div></section></div></div>
      {error && <div className="admin-lobby-feedback error" role="alert">{error}{conflict && <button onClick={() => setReload((n) => n + 1)}>读取服务器设置</button>}</div>}{message && <div className="admin-lobby-feedback" role="status">{message}</div>}
    </>}
  </main>;
}
