import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleHelp, RefreshCw, XCircle } from 'lucide-react';
import type { createAdminApi, ConfigHealth, HealthProcess } from '../api/client';
import { describe, LoadError } from '../users/shared';
import '../vision/lab.css';
import './ConfigHealthPage.css';

type Props = { api: ReturnType<typeof createAdminApi>; onUnauthorized: () => void };
const TITLES: Record<string, string> = { web: '网站服务', cron: '定时任务', admin: '管理后台' };
const LEVEL: Record<string, { tone: string; label: string; Icon: typeof CheckCircle2 }> = {
  ok: { tone: 'ok', label: '正常', Icon: CheckCircle2 }, warn: { tone: 'warn', label: '注意', Icon: AlertTriangle },
  bad: { tone: 'bad', label: '有问题', Icon: XCircle }, unknown: { tone: 'unknown', label: '未知', Icon: CircleHelp },
};
const minutes = (seconds: number | null) => seconds === null ? '' : seconds < 90 ? '1 分钟内' : `${Math.round(seconds / 60)} 分钟前`;

function ProcessCard({ item, staleMinutes }: { item: HealthProcess; staleMinutes: number }) {
  const state = item.state === 'never' ? ['bad', '从未上报'] : item.state === 'stale' ? ['warn', `上报已过期 · ${minutes(item.age_s)}`] : ['ok', minutes(item.age_s)];
  return <section className={`lab-panel ch-card ${item.state !== 'fresh' ? 'dim' : ''}`} aria-label={`${TITLES[item.process] ?? item.process} 体检`}>
    <div className="lab-panel-head"><h2>{TITLES[item.process] ?? item.process}<small className="mono">{item.process}</small></h2><span className={`lab-chip ${state[0]}`}>{state[1]}</span></div>
    <div className="ch-meta">{item.state === 'never' ? <span>这个进程还没有写过体检结果。可能未部署新版本，或进程没在运行。</span> : <><span>主机 <b className="mono">{item.hostname}</b></span><span>版本 <b className="mono">{item.build}</b></span></>}</div>
    {item.state === 'stale' && <div className="ch-stale">超过 {staleMinutes} 分钟没有更新，结论不再可信，已隐藏。只保留最后上报时间。</div>}
    {item.state === 'fresh' && <ul className="ch-list">{item.checks.map((check) => { const level = LEVEL[check.level] ?? LEVEL.unknown; return <li key={check.id} className={level.tone}><level.Icon aria-hidden="true" /><span>{check.message}<small className="mono">{check.id}</small></span><em>{level.label}</em></li>; })}
      {!item.checks.length && <li className="unknown"><CircleHelp aria-hidden="true" /><span>上报里没有任何检查项</span><em>未知</em></li>}</ul>}
  </section>;
}

export default function ConfigHealthPage({ api, onUnauthorized }: Props) {
  const [data, setData] = useState<ConfigHealth | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);
  const load = useCallback((signal?: AbortSignal) => {
    setBusy(true); setError('');
    api.configHealth(signal).then((next) => {
      if (!Array.isArray(next?.processes)) throw new Error('服务返回的体检结果格式不对');
      setData(next);
    }).catch((cause) => {
      if (cause instanceof DOMException && cause.name === 'AbortError') return;
      const { status, message } = describe(cause);
      if (status === 401) unauthorized.current(); else setError(message);
    }).finally(() => { if (!signal?.aborted) setBusy(false); });
  }, [api]);
  useEffect(() => { const controller = new AbortController(); load(controller.signal); return () => controller.abort(); }, [load]);

  const fresh = data?.processes.filter((p) => p.state === 'fresh').flatMap((p) => p.checks) ?? [];
  const missing = data?.processes.filter((p) => p.state === 'never').length ?? 0;
  const stale = data?.processes.filter((p) => p.state === 'stale').length ?? 0;
  const count = (level: string) => fresh.filter((c) => c.level === level).length;
  const version = data?.cross_checks.find((c) => c.id === 'build_consistency');
  const versionLevel = LEVEL[version?.level ?? 'unknown'] ?? LEVEL.unknown;
  const staleMinutes = Math.round((data?.stale_after_s ?? 1800) / 60);
  return <main className="lab-page ch-page">
    <div className="lab-heading"><div><h1>配置体检</h1><p>各进程定时自查生效配置，只上报结论、不上报配置值</p></div><span className="lab-status"><RefreshCw aria-hidden="true" />每 10 分钟上报 · {staleMinutes} 分钟未更新视为过期</span></div>
    <div className="lab-content">
      {error && <LoadError message={error} onRetry={() => load()} />}
      <section className="lab-panel ch-summary" aria-label="体检汇总">
        {data ? <div className="ch-counts"><span className="lab-chip bad"><XCircle aria-hidden="true" />{count('bad') + missing} 项有问题</span><span className="lab-chip warn"><AlertTriangle aria-hidden="true" />{count('warn')} 项注意</span><span className="lab-chip ok"><CheckCircle2 aria-hidden="true" />{count('ok')} 项正常</span>{count('unknown') > 0 && <span className="lab-chip"><CircleHelp aria-hidden="true" />{count('unknown')} 项未知</span>}{stale > 0 && <span className="lab-chip warn"><CircleHelp aria-hidden="true" />{stale} 个进程上报过期，结论未计入</span>}</div> : <span className="lab-note">{busy ? '正在读取体检结果' : '体检结果未读取'}</span>}
        {version && <div className={`ch-cross ${versionLevel.tone}`}><versionLevel.Icon aria-hidden="true" /><span>版本一致性：{version.message}</span></div>}
        <button className="lab-btn small" type="button" disabled={busy} onClick={() => load()}><RefreshCw aria-hidden="true" />刷新</button>
      </section>
      {data && <div className="ch-grid">{data.processes.map((item) => <ProcessCard key={item.process} item={item} staleMinutes={staleMinutes} />)}</div>}
      <p className="lab-note">不检查：SECRET_KEY（能上报就已通过启动闸）、外部服务是否连通（KataGo /health 会报假绿）、性能监控。</p>
    </div>
  </main>;
}
