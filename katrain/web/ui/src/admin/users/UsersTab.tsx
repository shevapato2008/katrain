import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Coins, Search } from 'lucide-react';
import { AdminApiError, type createAdminApi } from '../api/client';
import { describe, Dialog, LoadError, newKey, REASON_LABELS, when } from './shared';
import type { AdminUserDetail, AdminUserList, AdjustResult, LedgerRow, QuotaRow, RedeemedRow } from './types';

type Api = ReturnType<typeof createAdminApi>;
type Props = { api: Api; production: boolean; onUnauthorized: () => void };
const STATUS: Record<string, [string, string]> = { committed: ['ok', '已入账'], reserved: ['warn', '预扣中'], refunded: ['', '已退回'] };
const MAX_ADJUST = 12000;

export default function UsersTab({ api, production, onUnauthorized }: Props) {
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [list, setList] = useState<AdminUserList | null>(null);
  const [listError, setListError] = useState('');
  const [selected, setSelected] = useState<number | null>(null);
  const [attempt, setAttempt] = useState(0);
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);
  const failed = useCallback((cause: unknown, set: (message: string) => void) => {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    const { status, message } = describe(cause);
    if (status === 401) unauthorized.current(); else set(message);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setListError('');
      api.users(query, page, controller.signal).then((next) => {
        if (!Array.isArray(next?.items)) throw new Error('服务返回的用户列表格式不对');
        setList(next);
        setSelected((current) => current ?? next.items[0]?.id ?? null);
      }).catch((cause) => failed(cause, setListError));
    }, query ? 250 : 0);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [api, query, page, attempt, failed]);

  const pages = list ? Math.max(1, Math.ceil(list.total / list.page_size)) : 1;
  return <div className="ub-grid">
    <section className="lab-panel ub-list" aria-labelledby="ub-list-title">
      <div className="lab-panel-head"><h2 id="ub-list-title">用户</h2><small>{list ? `共 ${list.total.toLocaleString('zh-CN')} 人 · 第 ${list.page} / ${pages} 页` : '读取中'}</small></div>
      <div className="ub-search"><label className="ub-q"><Search aria-hidden="true" /><input value={query} maxLength={64} placeholder="用户名前缀、id 或 uuid" aria-label="搜索用户" onChange={(event) => { setQuery(event.target.value); setPage(1); }} /></label></div>
      {listError && <div className="ub-pad"><LoadError message={listError} onRetry={() => setAttempt((n) => n + 1)} /></div>}
      <div className="ub-thead"><span>id</span><span>用户名</span><span>段位</span><span className="num">余额</span><span>注册</span></div>
      <div className="ub-rows">
        {list?.items.map((user) => <button key={user.id} type="button" className={`ub-row ${user.id === selected ? 'on' : ''}`} aria-pressed={user.id === selected} onClick={() => setSelected(user.id)}>
          <span className="mono">{user.id}</span><span className="ub-name">{user.username}{user.is_admin && <span className="lab-chip">管理员</span>}</span><span>{user.rank ?? '—'}</span><span className="num">{user.credits}</span><span className="muted">{when(user.created_at, true)}</span>
        </button>)}
        {list && !list.items.length && <div className="lab-empty"><small>{query ? '没有匹配的用户' : '这个环境还没有用户'}</small></div>}
        {!list && !listError && <div className="lab-empty"><small>正在读取用户</small></div>}
      </div>
      <div className="ub-pager"><button className="lab-btn small" type="button" disabled={!list || page <= 1} onClick={() => setPage((n) => n - 1)}>上一页</button><span className="lab-note">每页 20 人</span><button className="lab-btn small" type="button" disabled={!list || page >= pages} onClick={() => setPage((n) => n + 1)}>下一页</button></div>
    </section>
    {selected !== null ? <UserDetail key={selected} api={api} userId={selected} production={production} failed={failed} onBalance={(balance) => setList((current) => current && { ...current, items: current.items.map((user) => user.id === selected ? { ...user, credits: balance } : user) })} />
      : <section className="lab-panel"><div className="lab-empty"><small>{list ? '选择一位用户查看详情' : ' '}</small></div></section>}
  </div>;
}

type DetailProps = { api: Api; userId: number; production: boolean; failed: (cause: unknown, set: (message: string) => void) => void; onBalance: (balance: number) => void };
function UserDetail({ api, userId, production, failed, onBalance }: DetailProps) {
  const [detail, setDetail] = useState<AdminUserDetail | null>(null);
  const [tab, setTab] = useState<'ledger' | 'quota' | 'redeemed'>('ledger');
  const [ledger, setLedger] = useState<LedgerRow[] | null>(null);
  const [next, setNext] = useState<number | null>(null);
  const [quota, setQuota] = useState<QuotaRow[] | null>(null);
  const [redeemed, setRedeemed] = useState<RedeemedRow[] | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [adjusting, setAdjusting] = useState(false);
  const [notice, setNotice] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    Promise.all([api.user(userId, controller.signal), api.userLedger(userId, null, controller.signal)]).then(([user, page]) => {
      setDetail(user); setLedger(page.items); setNext(page.next_before_id);
    }).catch((cause) => failed(cause, setError));
    return () => controller.abort();
  }, [api, userId, attempt, failed]);
  useEffect(() => {
    const controller = new AbortController();
    if (tab === 'quota' && quota === null) api.userQuota(userId, controller.signal).then((r) => setQuota(r.items)).catch((cause) => failed(cause, setError));
    if (tab === 'redeemed' && redeemed === null) api.userRedeemed(userId, controller.signal).then((r) => setRedeemed(r.items)).catch((cause) => failed(cause, setError));
    return () => controller.abort();
  }, [api, userId, tab, quota, redeemed, failed]);

  const more = () => { if (next) api.userLedger(userId, next).then((page) => { setLedger((rows) => [...(rows ?? []), ...page.items]); setNext(page.next_before_id); }).catch((cause) => failed(cause, setError)); };
  if (!detail) return <section className="lab-panel ub-detail">{error ? <div className="ub-pad"><LoadError message={error} onRetry={() => setAttempt((n) => n + 1)} /></div> : <div className="lab-empty"><small>正在读取用户详情</small></div>}</section>;
  return <section className="lab-panel ub-detail" aria-label={`用户 ${detail.username}`}>
    <div className="ub-dhead"><div><h2>{detail.username}{detail.is_admin && <span className="lab-chip">管理员</span>}</h2><p className="mono lab-note">id {detail.id} · uuid {detail.uuid}</p></div>
      <div className="ub-balance"><span className="lab-note">可用余额</span><strong className="num">{detail.credits}</strong><span className="lab-note">{detail.reserved.count ? `另预扣 ${detail.reserved.amount}` : '积分'}</span></div></div>
    <dl className="ub-facts"><div><dt>段位</dt><dd>{detail.rank ?? '—'}</dd></div><div><dt>注册时间</dt><dd>{when(detail.created_at, true)}</dd></div><div><dt>预扣中</dt><dd>{detail.reserved.count ? `${detail.reserved.amount} 积分 · ${detail.reserved.count} 笔` : '无'}</dd></div><div><dt>累计后台调整</dt><dd>{detail.admin_adjust_total > 0 ? '+' : ''}{detail.admin_adjust_total}</dd></div></dl>
    <div className="ub-actions"><button className="lab-btn primary" type="button" onClick={() => { setAdjusting(true); setNotice(''); }}><Coins aria-hidden="true" />调整积分</button><span className="lab-note">加或扣都追加一条账本行，不改历史</span></div>
    {notice && <div className="ub-pad"><div className="lab-banner ok" role="status"><CheckCircle2 aria-hidden="true" /><span>{notice}</span></div></div>}
    {error && <div className="ub-pad"><LoadError message={error} onRetry={() => setAttempt((n) => n + 1)} /></div>}
    <div className="lab-tabs" role="tablist">{([['ledger', '账本流水'], ['quota', '会员额度'], ['redeemed', '兑换记录']] as const).map(([id, text]) => <button key={id} className="lab-tab" type="button" role="tab" aria-selected={tab === id} onClick={() => setTab(id)}>{text}</button>)}</div>
    {tab === 'ledger' && <>
      <div className="ub-lhead"><span>时间</span><span>事由</span><span className="num">变动</span><span>状态</span><span className="num">余额</span></div>
      {ledger?.map((row) => { const [tone, label] = STATUS[row.status] ?? ['', row.status]; return <div key={row.id} className={`ub-lrow ${row.status === 'reserved' ? 'hold' : ''}`}>
        <span className="muted">{when(row.created_at)}</span><span>{REASON_LABELS[row.reason] ?? row.reason}<small title={row.ref_id}>{row.ref_id}</small></span>
        <span className={`num ${row.status === 'refunded' ? 'void' : row.delta > 0 ? 'plus' : ''}`}>{row.delta > 0 ? '+' : ''}{row.delta}</span>
        <span><span className={`lab-chip ${tone}`}>{label}</span></span><span className="num">{row.status === 'refunded' ? '—' : row.balance_after}</span></div>; })}
      {ledger && !ledger.length && <div className="lab-empty"><small>这个用户还没有任何账本记录</small></div>}
      <div className="ub-pager"><span className="lab-note">每次 50 条 · 预扣中的行高亮 · 已退回的预扣不计入余额</span><button className="lab-btn small" type="button" disabled={!next} onClick={more}>更早</button></div>
    </>}
    {tab === 'quota' && <div className="ub-quota">{quota === null ? <span className="lab-note">正在读取</span> : quota.length ? quota.map((row) => <div key={`${row.kind}-${row.period_key}`}><strong>{row.kind}</strong><span className="lab-note mono">{row.period_key}</span><div className="ub-bar"><i style={{ width: `${row.allowance ? Math.min(100, row.used / row.allowance * 100) : 0}%` }} /></div><span className="num">{row.used} / {row.allowance}</span></div>) : <span className="lab-note">还没有额度记录</span>}<p className="lab-note">只读 · 额度按周期自动换桶，不在后台编辑</p></div>}
    {tab === 'redeemed' && <>
      <div className="ub-lhead two"><span>兑换码</span><span className="num">面额</span><span>兑换时间</span></div>
      {redeemed === null ? <div className="lab-empty"><small>正在读取</small></div> : redeemed.length ? redeemed.map((row) => <div key={`${row.code}-${row.used_at}`} className="ub-lrow two"><span className="mono">{row.code}</span><span className="num">{row.credits}</span><span className="muted">{when(row.used_at)}</span></div>) : <div className="lab-empty"><small>没有兑换过兑换码</small></div>}
    </>}
    {adjusting && <AdjustDialog api={api} user={detail} production={production} onClose={() => setAdjusting(false)} onDone={(result, amount) => {
      setAdjusting(false); onBalance(result.balance);
      setNotice(result.replayed ? `这笔调整已经处理过（余额 ${result.balance}），没有重复入账。` : `已追加账本行 #${result.transaction_id}：${amount > 0 ? '+' : ''}${amount}，余额 ${result.balance}。`);
      setQuota(null); setAttempt((n) => n + 1);
    }} onUnauthorized={() => failed(new AdminApiError(401, ''), () => undefined)} />}
  </section>;
}

type AdjustProps = { api: Api; user: AdminUserDetail; production: boolean; onClose: () => void; onDone: (result: AdjustResult, amount: number) => void; onUnauthorized: () => void };
function AdjustDialog({ api, user, production, onClose, onDone, onUnauthorized }: AdjustProps) {
  const [amount, setAmount] = useState('');
  const [reason, setReason] = useState('');
  const [again, setAgain] = useState({ username: '', amount: '' });
  const [checked, setChecked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const key = useRef(newKey()); // one key per dialog: a retry after a lost response cannot double-apply
  const value = Number(amount);
  const valid = amount.trim() !== '' && Number.isInteger(value) && value !== 0;
  const amountError = !amount.trim() ? '' : !valid ? '请输入非零整数' : Math.abs(value) > MAX_ADJUST ? `单次绝对值不超过 ${MAX_ADJUST}` : value < 0 && -value > user.credits ? `余额只有 ${user.credits}，不能扣到负数` : '';
  const reasonError = reason && reason.trim().length < 5 ? '原因至少 5 个字' : '';
  const mismatch = (again.username || again.amount) && (again.username !== user.username || Number(again.amount) !== value || again.amount.trim() === '') ? '两次输入不一致：用户名与变动都要和上面相同' : '';
  const ready = valid && !amountError && reason.trim().length >= 5 && again.username === user.username && again.amount.trim() !== '' && Number(again.amount) === value && checked && !busy;
  const submit = async () => {
    setBusy(true); setError('');
    try {
      onDone(await api.adjustCredits(user.id, { amount: value, reason: reason.trim(), idempotency_key: key.current, confirm_username: again.username, confirm_amount: Number(again.amount) }), value);
    } catch (cause) {
      const { status, message } = describe(cause);
      if (status === 401) onUnauthorized(); else setError(message);
      setBusy(false);
    }
  };
  return <Dialog label={`调整 ${user.username} 的积分`} title={<>调整 {user.username} 的积分{production && <span className="lab-chip bad">生产环境</span>}</>} onClose={onClose} closable={!busy}
    actions={<><button className="lab-btn" type="button" disabled={busy} onClick={onClose}>返回</button><button className="lab-btn primary" type="button" disabled={!ready} onClick={() => { void submit(); }}>{busy ? '提交中' : '确认调整'}</button></>}>
    <div className="ub-adjform">
      <label className="lab-field">变动（正数加、负数扣，绝对值 ≤ {MAX_ADJUST}）<input inputMode="numeric" value={amount} onChange={(event) => setAmount(event.target.value.trim())} aria-invalid={!!amountError} />{amountError && <span className="ub-err"><AlertTriangle aria-hidden="true" />{amountError}</span>}</label>
      <label className="lab-field">原因（写进审计，至少 5 个字）<input value={reason} maxLength={200} onChange={(event) => setReason(event.target.value)} aria-invalid={!!reasonError} />{reasonError && <span className="ub-err"><AlertTriangle aria-hidden="true" />{reasonError}</span>}</label>
      <div className="ub-confirmbox"><p className="lab-note">再输入一次用户名和变动，与上面一致才能提交：</p>
        <label className="lab-field">用户名<input value={again.username} placeholder="再输入目标用户名" onChange={(event) => setAgain({ ...again, username: event.target.value })} /></label>
        <label className="lab-field">变动<input inputMode="numeric" value={again.amount} placeholder="再输入变动" onChange={(event) => setAgain({ ...again, amount: event.target.value.trim() })} /></label>
        {mismatch && <span className="ub-err"><AlertTriangle aria-hidden="true" />{mismatch}</span>}</div>
      <p className="lab-note">{valid && !amountError ? `余额 ${user.credits} → ${user.credits + value}。` : `当前余额 ${user.credits}。`}扣减不会让余额低于 0。</p>
      <label className="lab-check"><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} /><span>我已核对用户与金额。</span></label>
      {error && <LoadError message={error} />}
    </div>
  </Dialog>;
}
