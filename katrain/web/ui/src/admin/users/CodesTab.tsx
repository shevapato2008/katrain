import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Copy, FileDown, Ticket } from 'lucide-react';
import type { createAdminApi } from '../api/client';
import { describe, Dialog, LoadError, newKey, when } from './shared';
import type { CodeListing, CodesResult } from './types';

type Props = { api: ReturnType<typeof createAdminApi>; production: boolean; onUnauthorized: () => void };
const STATE: Record<string, [string, string]> = { used: ['', '已用'], unused: ['ok', '未用'], expired: ['warn', '已过期'] };
const DAY = 86_400_000;

export default function CodesTab({ api, production, onUnauthorized }: Props) {
  const [listing, setListing] = useState<CodeListing | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [form, setForm] = useState({ count: '20', credits: '100', days: '90', note: '' });
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [result, setResult] = useState<CodesResult | null>(null);
  const key = useRef(newKey());
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);
  const failed = useCallback((cause: unknown, set: (message: string) => void) => {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    const { status, message } = describe(cause);
    if (status === 401) unauthorized.current(); else set(message);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setError('');
    api.redeemCodes(controller.signal).then((next) => {
      if (!Array.isArray(next?.batches) || !Array.isArray(next?.codes)) throw new Error('服务返回的兑换码列表格式不对');
      setListing(next);
    }).catch((cause) => failed(cause, setError));
    return () => controller.abort();
  }, [api, attempt, failed]);

  const count = Number(form.count), credits = Number(form.credits), days = Number(form.days);
  const errors = {
    count: Number.isInteger(count) && count >= 1 && count <= 200 ? '' : '数量为 1–200 的整数',
    credits: Number.isInteger(credits) && credits >= 1 && credits <= 12000 ? '' : '面额为 1–12000 的整数',
    days: Number.isInteger(days) && days >= 1 && days <= 365 ? '' : '有效期为 1–365 天',
    note: form.note.trim().length >= 5 ? '' : '用途至少 5 个字',
  };
  const ready = !Object.values(errors).some(Boolean) && !busy;
  const submit = async () => {
    setBusy(true); setSubmitError('');
    try {
      const made = await api.generateCodes({ count, credits, days, note: form.note.trim(), idempotency_key: key.current });
      setResult(made); key.current = newKey(); setForm((current) => ({ ...current, note: '' }));
    } catch (cause) { failed(cause, setSubmitError); }
    setBusy(false);
  };
  const field = (name: keyof typeof form, label: string, extra = {}) => <label className={`lab-field ${name === 'note' ? 'ub-wide' : ''}`}>{label}
    <input value={form[name]} onChange={(event) => setForm({ ...form, [name]: event.target.value })} aria-invalid={!!(form[name] && errors[name])} {...extra} />
    {form[name] !== '' && errors[name] && name !== 'note' && <span className="ub-err"><AlertTriangle aria-hidden="true" />{errors[name]}</span>}
    {name === 'note' && form.note !== '' && errors.note && <span className="ub-err"><AlertTriangle aria-hidden="true" />{errors.note}</span>}</label>;
  return <div className="ub-codes">
    <section className="lab-panel" aria-labelledby="ub-gen-title">
      <div className="lab-panel-head"><h2 id="ub-gen-title">生成一批兑换码</h2><small>码值只在生成后显示一次</small></div>
      <div className="ub-genform">
        {field('count', '数量（1–200）', { inputMode: 'numeric' })}{field('credits', '每个面额（1–12000 积分）', { inputMode: 'numeric' })}{field('days', '有效期（天，≤365）', { inputMode: 'numeric' })}{field('note', '用途（写进审计，至少 5 个字）', { maxLength: 200, placeholder: '例如：九月线下活动奖品' })}
        <div className="ub-gensum"><span className="lab-note">{errors.count || errors.credits || errors.days ? '请先填好数量、面额与有效期' : <>合计 <strong>{count * credits}</strong> 积分 · 到期 {when(new Date(Date.now() + days * DAY).toISOString(), true)}</>}</span>
          <button className="lab-btn primary" type="button" disabled={!ready} onClick={() => { void submit(); }}><Ticket aria-hidden="true" />{busy ? '生成中' : '生成'}</button></div>
        {submitError && <div className="ub-wide-all"><LoadError message={submitError} /></div>}
      </div>
    </section>
    <section className="lab-panel" aria-labelledby="ub-codes-title">
      <div className="lab-panel-head"><h2 id="ub-codes-title">已生成的兑换码</h2><small>码值已打码 · 不提供再次查看</small></div>
      {error && <div className="ub-pad"><LoadError message={error} onRetry={() => setAttempt((n) => n + 1)} /></div>}
      {!listing && !error && <div className="lab-empty"><small>正在读取兑换码</small></div>}
      {listing && <>
        {listing.batches.length > 0 && <div className="ub-batches">{listing.batches.map((batch) => <div key={`${batch.expires_at}-${batch.credits}`}><strong>{when(batch.created_at)}</strong><span>{batch.count} 个 × {batch.credits} 积分</span><span className="lab-note">到期 {when(batch.expires_at, true)}</span><span className={`lab-chip ${batch.used === batch.count ? '' : 'ok'}`}>已用 {batch.used} / {batch.count}</span><span className="lab-note ub-ellipsis">{batch.note ?? '—'}{batch.created_by ? ` · ${batch.created_by}` : ''}</span></div>)}</div>}
        <div className="ub-lhead codes"><span>兑换码</span><span className="num">面额</span><span>到期</span><span>状态</span><span>使用者</span><span>使用时间</span></div>
        {listing.codes.map((code, index) => { const [tone, label] = STATE[code.state] ?? ['', code.state]; return <div key={`${code.code}-${index}`} className="ub-lrow codes"><span className="mono">{code.code}</span><span className="num">{code.credits}</span><span className="muted">{when(code.expires_at, true)}</span><span><span className={`lab-chip ${tone}`}>{label}</span></span><span>{code.used_by ?? '—'}</span><span className="muted">{when(code.used_at)}</span></div>; })}
        {!listing.codes.length && <div className="lab-empty"><small>还没有生成过兑换码</small></div>}
      </>}
    </section>
    {result && <OneTimeCodes result={result} production={production} onClose={() => { setResult(null); setAttempt((n) => n + 1); }} />}
  </div>;
}

function OneTimeCodes({ result, production, onClose }: { result: CodesResult; production: boolean; onClose: () => void }) {
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState('');
  const text = result.codes.join('\n');
  const download = () => {
    const csv = `code,credits,expires_at\n${result.codes.map((code) => `${code},${result.credits},${result.expires_at}`).join('\n')}\n`;
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url; link.download = `redeem-codes-${result.expires_at.slice(0, 10)}-${result.count}x${result.credits}.csv`;
    link.click(); URL.revokeObjectURL(url);
  };
  const copy = () => { navigator.clipboard?.writeText(text).then(() => setCopied('已复制')).catch(() => setCopied('复制失败，请手动选中')); };
  return <Dialog label={`已生成 ${result.count} 个兑换码`} title={<>已生成 {result.count} 个兑换码{production && <span className="lab-chip bad">生产环境</span>}</>} onClose={onClose} closable={saved}
    actions={<button className="lab-btn" type="button" disabled={!saved} onClick={onClose}>关闭</button>}>
    <p className="lab-note">码值只显示这一次，每个 {result.credits} 积分，到期 {when(result.expires_at, true)}。关闭后列表里只剩打码后的样子。</p>
    <pre className="ub-codelist" aria-label="本批兑换码">{text}</pre>
    <div className="ub-actions flush"><button className="lab-btn primary" type="button" onClick={download}><FileDown aria-hidden="true" />下载 CSV</button><button className="lab-btn" type="button" onClick={copy}><Copy aria-hidden="true" />复制全部</button>{copied && <span className="lab-note" role="status">{copied}</span>}</div>
    <label className="lab-check"><input type="checkbox" checked={saved} onChange={(event) => setSaved(event.target.checked)} /><span>我已保存这批码值。</span></label>
  </Dialog>;
}
