import { useEffect, useRef, useState } from 'react';
import { FileDown, Search, ShieldCheck } from 'lucide-react';
import type { createAdminApi } from '../api/client';
import { ACTION_LABELS, describe, LoadError, when } from './shared';
import type { AuditPage as AuditResult, AuditQuery, AuditRow } from './types';
import '../vision/lab.css';
import './UsersPage.css';

type Props = { api: ReturnType<typeof createAdminApi>; onUnauthorized: () => void };

function summary(row: AuditRow): string {
  const d = row.detail;
  if (!d || typeof d !== 'object') return typeof d === 'string' && d ? d : '—';
  const v = d as Record<string, unknown>;
  if (row.action === 'credit_adjust') return `${Number(v.amount) > 0 ? '+' : ''}${v.amount} · ${v.reason} · 余额 ${v.balance_before}→${v.balance_after}`;
  if (row.action === 'redeem_codes_generate') return `${v.count} 个 × ${v.credits} 积分 · ${v.note} · 到期 ${when(String(v.expires_at), true)}`;
  return Object.entries(v).map(([k, value]) => `${k}: ${String(value)}`).join(' · ');
}
function target(row: AuditRow): string {
  if (row.target_type === 'user') return `用户 ${row.target_id}${row.target_label ? ` · ${row.target_label}` : ''}`;
  if (row.target_type === 'redeem_batch') return '兑换码批次';
  if (row.target_type) return `${row.target_type} ${row.target_id ?? ''}`.trim();
  return '—';
}

export default function AuditPage({ api, onUnauthorized }: Props) {
  const [draft, setDraft] = useState<AuditQuery>({ action: '', since: '', until: '', target_user_id: '' });
  const [query, setQuery] = useState<AuditQuery>({ page: 1 });
  const [result, setResult] = useState<AuditResult | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [exporting, setExporting] = useState(false);
  const [exported, setExported] = useState('');
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    api.audit(query, controller.signal).then((next) => {
      if (!Array.isArray(next?.items)) throw new Error('服务返回的审计记录格式不对');
      setResult(next);
    }).catch((cause) => {
      if (cause instanceof DOMException && cause.name === 'AbortError') return;
      const { status, message } = describe(cause);
      if (status === 401) unauthorized.current(); else setError(message);
    });
    return () => controller.abort();
  }, [api, query, attempt]);
  const exportCsv = async () => {
    setExporting(true); setExported(''); setError('');
    try {
      const { blob, rows, total } = await api.auditExport(query);
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `admin-audit-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click(); URL.revokeObjectURL(url);
      setExported(rows < total ? `已导出最新的 ${rows} 条（共 ${total} 条，单次上限 1 万条；缩小时间范围可导出更早的）` : `已导出 ${rows} 条；这次导出本身也记入了审计`);
    } catch (cause) {
      const { status, message } = describe(cause);
      if (status === 401) unauthorized.current(); else setError(message);
    }
    setExporting(false);
  };
  const page = query.page ?? 1;
  const pages = result ? Math.max(1, Math.ceil(result.total / result.page_size)) : 1;
  const badTarget = !!draft.target_user_id && !/^\d+$/.test(draft.target_user_id);
  return <main className="lab-page ub-page">
    <div className="lab-heading"><div><h1>审计日志</h1><p>后台账号的登录与每一次写入，只读</p></div><span className="lab-status"><ShieldCheck aria-hidden="true" />与业务写入同一事务提交</span></div>
    <div className="lab-content">
      <form className="lab-panel au-filter" onSubmit={(event) => { event.preventDefault(); if (!badTarget) setQuery({ ...draft, page: 1 }); }}>
        <label className="lab-field">动作<select value={draft.action} onChange={(event) => setDraft({ ...draft, action: event.target.value })}><option value="">全部</option>{Object.entries(ACTION_LABELS).map(([id, text]) => <option key={id} value={id}>{text}</option>)}</select></label>
        <label className="lab-field">起<input type="date" value={draft.since} onChange={(event) => setDraft({ ...draft, since: event.target.value })} /></label>
        <label className="lab-field">止<input type="date" value={draft.until} onChange={(event) => setDraft({ ...draft, until: event.target.value })} /></label>
        <label className="lab-field">目标用户 id<input inputMode="numeric" placeholder="例如 3" value={draft.target_user_id} aria-invalid={badTarget} onChange={(event) => setDraft({ ...draft, target_user_id: event.target.value.trim() })} /></label>
        <button className="lab-btn" type="submit" disabled={badTarget}><Search aria-hidden="true" />筛选</button>
        <button className="lab-btn" type="button" disabled={exporting || !result?.total} onClick={() => { void exportCsv(); }}><FileDown aria-hidden="true" />{exporting ? '导出中' : '导出 CSV'}</button>
      </form>
      {exported && <div className="lab-banner ok" role="status"><span>{exported}</span></div>}
      <section className="lab-panel" aria-labelledby="au-title">
        <div className="lab-panel-head"><h2 id="au-title">记录</h2><small>{result ? `${result.total} 条 · 按时间倒序` : '读取中'}</small></div>
        {error && <div className="ub-pad"><LoadError message={error} onRetry={() => setAttempt((n) => n + 1)} /></div>}
        <div className="ub-lhead audit"><span>时间</span><span>操作者</span><span>动作</span><span>目标</span><span>结果</span><span>详情</span></div>
        {result?.items.map((row) => <div key={row.id} className="ub-lrow audit"><span className="muted mono">{when(row.created_at)}</span><span>{row.actor_username}</span><span>{ACTION_LABELS[row.action] ?? row.action}<small>{row.action}</small></span><span>{target(row)}</span><span><span className={`lab-chip ${row.success ? 'ok' : 'bad'}`}>{row.success ? '成功' : '失败'}</span></span><span className="muted ub-wrap">{summary(row)}</span></div>)}
        {result && !result.items.length && <div className="lab-empty"><small>没有符合条件的记录</small></div>}
        {!result && !error && <div className="lab-empty"><small>正在读取审计记录</small></div>}
        <div className="ub-pager"><button className="lab-btn small" type="button" disabled={page <= 1} onClick={() => setQuery({ ...query, page: page - 1 })}>上一页</button><span className="lab-note">每页 50 条 · 第 {page} / {pages} 页</span><button className="lab-btn small" type="button" disabled={page >= pages} onClick={() => setQuery({ ...query, page: page + 1 })}>下一页</button></div>
      </section>
    </div>
  </main>;
}
