import { useCallback, useEffect, useRef, useState } from 'react';
import { Info } from 'lucide-react';
import type { BoxDeviceRow, createAdminApi, DeviceFleet } from '../api/client';
import { describe, Dialog, LoadError, when } from '../users/shared';
import '../vision/lab.css';
import '../users/UsersPage.css';
import './DevicesPage.css';

type Props = { api: ReturnType<typeof createAdminApi>; production: boolean; onUnauthorized: () => void };
const STATE: Record<string, [string, string]> = { online: ['ok', '在线'], offline: ['warn', '失联'], never: ['', '从未上报'], pending: ['info', '待批准'], rejected: ['bad', '已拒绝'] };

function ago(seconds: number | null): string {
  if (seconds === null) return '从未上报';
  if (seconds < 60) return '刚刚';
  if (seconds < 3600) return `${Math.round(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} 小时前`;
  return `${Math.round(seconds / 86400)} 天前`;
}
function uptime(seconds: number | null): string {
  if (seconds === null) return '—';
  const days = Math.floor(seconds / 86400), hours = Math.floor((seconds % 86400) / 3600);
  return days ? `${days} 天 ${hours} 小时` : hours ? `${hours} 小时` : `${Math.round(seconds / 60)} 分钟`;
}
const spread = (counts: Record<string, number>) => Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([name, n]) => `${name} × ${n}`).join(' · ') || '—';

export default function DevicesPage({ api, production, onUnauthorized }: Props) {
  const [fleet, setFleet] = useState<DeviceFleet | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [deciding, setDeciding] = useState<{ device: BoxDeviceRow; decision: 'approve' | 'reject' } | null>(null);
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
    api.devices(controller.signal).then((next) => {
      if (!Array.isArray(next?.devices)) throw new Error('服务返回的设备列表格式不对');
      setFleet(next);
    }).catch((cause) => failed(cause, setError));
    return () => controller.abort();
  }, [api, attempt, failed]);

  const pending = fleet?.devices.filter((d) => d.state === 'pending') ?? [];
  const known = fleet?.devices.filter((d) => d.status === 'approved') ?? [];
  const rejected = fleet?.devices.filter((d) => d.state === 'rejected') ?? [];
  const count = (state: string) => fleet?.counts[state] ?? 0;
  return <main className="lab-page ub-page dv-page">
    <div className="lab-heading"><div><h1>盒子设备</h1><p>出厂盒子每 5 分钟用设备密钥签名上报一次，只报版本与状态</p></div><span className="lab-status"><Info aria-hidden="true" />{Math.round((fleet?.online_within_s ?? 900) / 60)} 分钟内有上报算在线</span></div>
    <div className="lab-content">
      {error && <LoadError message={error} onRetry={() => setAttempt((n) => n + 1)} />}
      <section className="lab-panel dv-summary" aria-label="设备汇总">
        {fleet ? <><div className="dv-counts"><span className="lab-chip ok">{count('online')} 台在线</span><span className="lab-chip warn">{count('offline')} 台失联</span><span className="lab-chip">{count('never')} 台从未上报</span><span className="lab-chip info">{count('pending')} 台待批准</span></div>
          <span className="lab-note">smartbox 版本：{spread(fleet.versions.smartbox)}</span><span className="lab-note">katrain：{spread(fleet.versions.katrain)}</span></> : <span className="lab-note">{error ? '设备列表未读取' : '正在读取设备'}</span>}
      </section>
      {pending.length > 0 && <section className="lab-panel" aria-labelledby="dv-pending-title">
        <div className="lab-panel-head"><h2 id="dv-pending-title">待批准</h2><small>首次上报自动登记；确认是自家出厂设备后再批准</small></div>
        {pending.map((device) => <div key={device.device_id} className="dv-pend"><span className="mono">{device.device_id}</span><span>{device.board ?? '—'}</span><span className="lab-note">登记于 {when(device.registered_at)}{device.last_ip ? ` · 来自 ${device.last_ip}` : ''}</span>
          <span className="dv-act"><button className="lab-btn small" type="button" onClick={() => setDeciding({ device, decision: 'reject' })}>拒绝</button><button className="lab-btn small primary" type="button" onClick={() => setDeciding({ device, decision: 'approve' })}>批准</button></span></div>)}
      </section>}
      <section className="lab-panel" aria-labelledby="dv-list-title">
        <div className="lab-panel-head"><h2 id="dv-list-title">设备</h2><small>{known.length} 台已批准{rejected.length ? ` · ${rejected.length} 台已拒绝` : ''}</small></div>
        <div className="ub-lhead dv"><span>设备</span><span>状态</span><span>板型</span><span>smartbox</span><span>katrain</span><span>模式</span><span>最近上报</span><span>开机时长</span><span>IP</span></div>
        {[...known, ...rejected].map((d) => { const [tone, label] = STATE[d.state] ?? ['', d.state]; return <div key={d.device_id} className="ub-lrow dv"><span className="mono">{d.device_id}</span><span><span className={`lab-chip ${tone}`}>{label}</span></span><span>{d.board ?? '—'}</span><span className="mono">{d.smartbox_version ?? '—'}</span><span className="mono">{d.katrain_build ?? '—'}</span><span>{d.mode ?? '—'}</span><span className="muted">{ago(d.silent_s)}</span><span className="muted">{d.state === 'online' ? uptime(d.uptime_s) : '—'}</span><span className="mono muted">{d.last_ip ?? '—'}</span></div>; })}
        {fleet && !known.length && !rejected.length && <div className="lab-empty"><small>还没有批准的设备。盒子联网启动后会自动出现在「待批准」里。</small></div>}
      </section>
    </div>
    {deciding && <DecideDialog api={api} production={production} {...deciding} onClose={() => setDeciding(null)} onDone={() => { setDeciding(null); setAttempt((n) => n + 1); }} onUnauthorized={() => unauthorized.current()} />}
  </main>;
}

function DecideDialog({ api, device, decision, production, onClose, onDone, onUnauthorized }: { api: ReturnType<typeof createAdminApi>; device: BoxDeviceRow; decision: 'approve' | 'reject'; production: boolean; onClose: () => void; onDone: () => void; onUnauthorized: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const verb = decision === 'approve' ? '批准' : '拒绝';
  const submit = async () => {
    setBusy(true); setError('');
    try { await api.decideDevice(device.device_id, decision); onDone(); } catch (cause) {
      const { status, message } = describe(cause);
      if (status === 401) onUnauthorized(); else setError(message);
      setBusy(false);
    }
  };
  return <Dialog label={`${verb}设备 ${device.device_id}`} title={<>{verb}设备 {device.device_id}{production && <span className="lab-chip bad">生产环境</span>}</>} onClose={onClose} closable={!busy}
    actions={<><button className="lab-btn" type="button" disabled={busy} onClick={onClose}>返回</button><button className={`lab-btn ${decision === 'approve' ? 'primary' : ''}`} type="button" disabled={busy} onClick={() => { void submit(); }}>{busy ? '提交中' : `确认${verb}`}</button></>}>
    <p className="lab-note">{decision === 'approve' ? '批准后这台盒子的上报会进入设备列表。只批准能对上出厂记录的设备。' : '拒绝后这台盒子的上报一律被拒，需要重新出厂登记才能恢复。'}操作会写入审计。</p>
    <p className="lab-note mono">板型 {device.board ?? '—'} · 登记于 {when(device.registered_at)}{device.last_ip ? ` · 来自 ${device.last_ip}` : ''}</p>
    {error && <LoadError message={error} />}
  </Dialog>;
}
