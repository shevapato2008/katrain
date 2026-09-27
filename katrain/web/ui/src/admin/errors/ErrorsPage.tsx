import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Info } from 'lucide-react';
import type { createAdminApi, ErrorGroupRow, ErrorList } from '../api/client';
import { describe, LoadError, when } from '../users/shared';
import '../vision/lab.css';
import './ErrorsPage.css';

type Props = { api: ReturnType<typeof createAdminApi>; onUnauthorized: () => void; onChanged: () => void };
type Status = 'open' | 'resolved' | 'all';
const TITLES: Record<string, string> = { web: '网站服务', cron: '定时任务', admin: '管理后台' };
const DAY_MS = 86_400_000;

function ago(iso: string | null): string {
  if (!iso) return '—';
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 60) return `${Math.round(seconds)} 秒前`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时前`;
  return when(iso);
}
const recent = (group: ErrorGroupRow) => !group.resolved_at && !!group.state_changed_at && Date.now() - new Date(group.state_changed_at).getTime() < DAY_MS;

export default function ErrorsPage({ api, onUnauthorized, onChanged }: Props) {
  const [status, setStatus] = useState<Status>('open');
  const [process, setProcess] = useState('');
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ErrorList | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);
  const failed = useCallback((cause: unknown) => {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    const { status: code, message } = describe(cause);
    if (code === 401) unauthorized.current(); else setError(message);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    api.errors({ status, process, page }, controller.signal).then((next) => {
      if (!Array.isArray(next?.items)) throw new Error('服务返回的报错列表格式不对');
      setData(next);
      setSelected((current) => next.items.some((item) => item.id === current) ? current : next.items[0]?.id ?? null);
    }).catch(failed);
    return () => controller.abort();
  }, [api, status, process, page, attempt, failed]);

  const resolve = async (id: number) => {
    setBusy(true); setError('');
    try { await api.resolveError(id); setAttempt((n) => n + 1); onChanged(); } catch (cause) { failed(cause); }
    setBusy(false);
  };
  const collectors = data ? (['web', 'cron', 'admin'] as const).map((name) => ({ name, ...(data.collectors[name] ?? { state: 'never' as const }) })) : [];
  const blind = collectors.some((c) => c.state !== 'fresh' || c.last_flush_ok === false);
  const group = data?.items.find((item) => item.id === selected);
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return <main className="lab-page er-page">
    <div className="lab-heading"><div><h1>报错追踪</h1><p>网站、定时任务、后台三个进程的 ERROR 日志，按指纹聚合</p></div><span className="lab-status"><Info aria-hidden="true" />保留 30 天 · 最多 5000 组 · 告警只在后台内提示</span></div>
    <div className="lab-content">
      {error && <LoadError message={error} onRetry={() => setAttempt((n) => n + 1)} />}
      <section className="lab-panel er-collectors" aria-label="采集器状态">
        {data ? collectors.map((c) => { const ok = c.state === 'fresh' && c.last_flush_ok !== false; return <span key={c.name} className={`er-col ${ok ? 'ok' : 'warn'}`}>{ok ? <CheckCircle2 aria-hidden="true" /> : <AlertTriangle aria-hidden="true" />}<b>{TITLES[c.name]}</b>
          <small>采集器 · {c.state === 'never' ? '从未上报' : c.state === 'stale' ? `上报已过期 · ${Math.round((c.age_s ?? 0) / 60)} 分钟前` : c.last_flush_ok === false ? '最近一次写库失败' : `${ago(c.last_flush_at ?? null)}刷写 · 丢弃 ${c.dropped ?? 0}${c.overflow ? ` · 超上限 ${c.overflow}` : ''}`}</small></span>; }) : <span className="lab-note">正在读取采集器状态</span>}
      </section>
      <div className="er-grid">
        <section className="lab-panel er-list" aria-label="报错分组">
          <div className="lab-panel-head"><div className="er-seg" role="group" aria-label="状态">{([['open', '未解决'], ['resolved', '已解决'], ['all', '全部']] as const).map(([value, text]) => <button key={value} type="button" aria-pressed={status === value} onClick={() => { setStatus(value); setPage(1); }}>{text}</button>)}</div>
            <select className="er-proc" aria-label="进程" value={process} onChange={(event) => { setProcess(event.target.value); setPage(1); }}><option value="">全部进程</option><option value="web">web</option><option value="cron">cron</option><option value="admin">admin</option></select></div>
          {data?.items.map((item) => <button key={item.id} type="button" className={`er-row ${item.id === group?.id ? 'on' : ''}`} aria-pressed={item.id === group?.id} onClick={() => setSelected(item.id)}>
            <span className="er-count">{item.count}</span>
            <span className="er-main"><strong>{item.template}</strong><small className="mono">{item.exc_type ? `${item.exc_type} · ` : ''}{item.location}</small></span>
            <span className="er-side"><span className="lab-chip">{item.process}</span>{item.resolved_at ? <span className="lab-chip ok">已解决</span> : recent(item) && (item.first_seen === item.state_changed_at ? <span className="lab-chip bad">新</span> : <span className="lab-chip warn">重新出现</span>)}<small>{ago(item.last_seen)}</small></span>
          </button>)}
          {data && !data.items.length && <div className="lab-empty"><small>{blind ? '有采集器未在上报：列表为空不代表没有报错' : status === 'resolved' ? '没有已解决的报错' : '没有未解决的报错'}</small></div>}
          {!data && !error && <div className="lab-empty"><small>正在读取报错</small></div>}
          <div className="ub-pager"><button className="lab-btn small" type="button" disabled={page <= 1} onClick={() => setPage((n) => n - 1)}>上一页</button><span className="lab-note">{data ? `${data.total} 组 · 按最近出现排序` : ''}</span><button className="lab-btn small" type="button" disabled={page >= pages} onClick={() => setPage((n) => n + 1)}>下一页</button></div>
        </section>
        {group ? <section className="lab-panel er-detail" aria-label="报错详情">
          <div className="lab-panel-head"><h2>{group.template}</h2>{group.resolved_at ? <span className="lab-chip ok">已由 {group.resolved_by} 标记解决</span> : <button className="lab-btn small" type="button" disabled={busy} onClick={() => { void resolve(group.id); }}><CheckCircle2 aria-hidden="true" />标记已解决</button>}</div>
          <dl className="er-facts"><div><dt>进程</dt><dd>{group.process}{group.job ? ` · 任务 ${group.job}` : ''}</dd></div><div><dt>次数</dt><dd>{group.count}</dd></div><div><dt>首次</dt><dd>{when(group.first_seen)}</dd></div><div><dt>最近</dt><dd>{ago(group.last_seen)}</dd></div><div><dt>版本</dt><dd className="mono">{group.build}</dd></div></dl>
          <div className="er-loc"><span className="lab-note">位置（最内三帧）</span><code>{group.location}</code></div>
          <pre className="er-sample">{group.sample}</pre>
          <p className="lab-note er-pad">样本已脱敏（手机号、邮箱、令牌、key= / password=），不含请求体与请求头。再次出现会自动重新打开。</p>
        </section> : <section className="lab-panel"><div className="lab-empty">{data && (blind ? <><AlertTriangle aria-hidden="true" /><span>有采集器未在上报，不能据此判断没有报错</span></> : <><CheckCircle2 aria-hidden="true" /><span>{status === 'resolved' ? '没有已解决的报错' : '没有未解决的报错'}</span></>)}</div></section>}
      </div>
    </div>
  </main>;
}
