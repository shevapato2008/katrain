import { useState } from 'react';
import { Activity, CheckCircle2, CircleDashed, Clock3, PauseCircle, TriangleAlert, WifiOff, XCircle } from 'lucide-react';
import { jobDescriptions, jobLabels } from './jobLabels';
import type { CronHealth, CronJob, CronRun, CronView } from './types';
import './CronPage.css';

const statusLabels: Record<CronHealth, string> = { ok: '正常', running: '运行中', errors: '有报错', failed: '失败', offline: '失联', stuck: '卡住', overdue: '该跑没跑', disabled: '已停用', pending: '等待首次运行' };
const shortStatusLabels: Record<CronHealth, string> = { ...statusLabels, errors: '报错', overdue: '逾期', pending: '待首跑', disabled: '停用' };
const statusIcons = { ok: CheckCircle2, running: Activity, errors: TriangleAlert, failed: XCircle, offline: WifiOff, stuck: TriangleAlert, overdue: Clock3, disabled: PauseCircle, pending: CircleDashed };
const summaryOrder: CronHealth[] = ['failed', 'offline', 'stuck', 'errors', 'overdue', 'running', 'pending', 'disabled', 'ok'];
const exceptionStates = new Set<CronHealth>(['failed', 'errors', 'offline', 'stuck', 'overdue']);
const time = (value: string | null) => value ? new Date(value).toLocaleTimeString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' }) : '—';
const runTime = (value: string) => new Date(value).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, timeZone: 'Asia/Shanghai' });
const duration = (value: number | null, kind: CronJob['kind']) => kind === 'loop' ? '循环中' : value === null ? '—' : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} 秒`;
const interval = (job: CronJob) => job.kind === 'loop' ? '常驻循环' : `间隔 · ${job.interval_seconds === 3 ? '3 秒' : job.interval_seconds === 900 ? '15 分' : job.interval_seconds === 1800 ? '30 分' : job.interval_seconds === 300 ? '5 分' : job.interval_seconds === 3600 ? '1 小时' : job.interval_seconds === 86400 ? '1 天' : `${job.interval_seconds} 秒`}`;
const runStatus = (run: CronRun) => run.status === 'success' ? '成功' : run.status === 'failed' ? '失败' : run.status === 'errors' ? '有报错' : '运行中';
const elapsed = (from: string | null, to: string | null) => {
  if (!from || !to) return '时间未知';
  const seconds = Math.max(0, Math.floor((new Date(to).getTime() - new Date(from).getTime()) / 1000));
  if (seconds < 60) return `${seconds} 秒`;
  const minutes = Math.floor(seconds / 60);
  return seconds % 60 ? `${minutes} 分 ${seconds % 60} 秒` : `${minutes} 分钟`;
};
const queueSummary = (pending: number, oldest: string | null, observed: string | null) => pending ? `待处理 ${pending} · 最早等待 ${elapsed(oldest, observed)}` : '待处理 0 · 暂无等待';
const fullTime = (value: string | null) => value ? runTime(value) : '暂无记录';
const cadence = (job: CronJob) => job.kind === 'loop' ? '常驻循环' : `${interval(job).replace('间隔 · ', '每 ')}执行`;

function StatusIcon({ state }: { state: CronHealth }) {
  const Icon = statusIcons[state];
  return <Icon aria-hidden="true" />;
}

export default function CronPage({ view, onRefresh, onSelectJob }: { view: CronView; onRefresh: () => void; onSelectJob?: (name: string) => void }) {
  const [selected, setSelected] = useState<string | null>(view.selectedJob ?? null);
  const [feedback, setFeedback] = useState('');
  const selectedJob = view.jobs.find((job) => job.name === selected);
  const runs = selected ? view.runs[selected] ?? [] : [];
  const statusCounts = view.jobs.reduce<Partial<Record<CronHealth, number>>>((counts, job) => { counts[job.health.state] = (counts[job.health.state] ?? 0) + 1; return counts; }, {});
  const displayedJobs = [...view.jobs.filter((job) => exceptionStates.has(job.health.state)), ...view.jobs.filter((job) => !exceptionStates.has(job.health.state))];
  const processJob = view.jobs[0];
  const offline = view.state === 'offline' || view.jobs.some((job) => job.health.state === 'offline');
  const heartbeat = elapsed(processJob?.heartbeat_at ?? null, view.observed_at);
  const processStarted = processJob?.process_started_at ? time(processJob.process_started_at).slice(0, 5) : '未知';
  const refresh = () => { setFeedback('正在重新检查；当前数据仍为上次采样。'); onRefresh(); };
  return <main className="cron-page" data-testid="cron-view" data-state={view.state}>
    <div className="cron-heading"><div><h1>定时任务</h1><div className="cron-sub">观察 cron 进程、任务和分析队列</div></div><div className="cron-heading-actions"><span>{view.state === 'loading' ? '首次读取中 · 每 15 秒刷新' : view.state === 'api-error' ? view.observed_at ? `数据停在 ${time(view.observed_at)} · 正在重试` : '首次读取失败 · 每 15 秒重试' : view.observed_at ? `采样于 ${time(view.observed_at)} · 每 15 秒刷新` : '尚无采样 · 每 15 秒重试'}</span><button className="cron-refresh" onClick={refresh}>刷新状态</button></div></div>
    <div className="cron-content">
      {feedback && <div className="cron-feedback" role="status">{feedback}</div>}
      {view.state === 'signin' ? <div className="cron-empty"><h2>登录管理后台</h2><p>通过 SSH 隧道访问的后台专用账号，与公开 Galaxy 账号独立。</p></div> :
      view.state === 'loading' ? <div className="cron-loading" role="status"><h2>正在读取任务状态…</h2><p>首次采样尚未完成，进程和任务健康状态暂时未知。</p>{[1, 2, 3, 4].map((n) => <div className="cron-skeleton" key={n} />)}</div> :
      view.state === 'no-table' || view.state === 'empty' || view.jobs.length === 0 ? <div className="cron-empty" role={view.state === 'api-error' ? 'alert' : undefined}><h2>{view.state === 'no-table' ? '状态表尚未建立' : view.state === 'api-error' ? '任务状态读取失败' : 'cron 进程还没上报任务'}</h2><p>{view.state === 'no-table' ? view.error ?? 'katrain-web 新版本可能还没启动。此页面不能判断 cron 是否正常。' : view.state === 'api-error' ? view.error ?? '请求失败，请重试。' : 'cron 进程还没上报过，可能新版 cron 还没部署。当前无法判断任务健康状态。'}</p><button onClick={refresh}>重新检查</button></div> : <>
        {(view.state === 'api-error' || view.state === 'offline') && <div className="cron-notice" role="alert"><strong>{view.state === 'offline' ? 'cron 进程失联' : view.error ?? '数据暂不可用'}</strong><span>{view.state === 'offline' ? '最后心跳已超过 120 秒，正在保留最后采样的运行时间供排查。' : `上次成功读取于 ${time(view.observed_at)} · 当前显示的是旧数据`}</span></div>}
        <div className="cron-process">
          <div className="cron-overview-card">
            <div className="cron-eyebrow">CRON 进程</div>
            <div className={`cron-process-strong ${view.state === 'api-error' ? 'uncertain' : offline ? 'offline' : 'online'}`}>
              {view.state === 'api-error' ? <TriangleAlert aria-hidden="true" /> : offline ? <WifiOff aria-hidden="true" /> : <Activity aria-hidden="true" />}
              {view.state === 'api-error' ? '状态待确认' : offline ? '进程失联' : '进程在线'}
            </div>
            <div className="cron-process-small">{view.state === 'api-error' ? `上次心跳 ${time(processJob?.heartbeat_at ?? null)}` : offline ? `最后心跳 ${heartbeat}前` : `心跳 ${heartbeat}前 · ${processStarted} 启动`}</div>
          </div>
          <div className="cron-overview-card" role="group" aria-label="任务概况">
            <div className="cron-eyebrow">任务概况 · {view.jobs.length} 项</div>
            <div className="cron-summary-chips">{summaryOrder.filter((state) => statusCounts[state]).map((state) => <span key={state} className={`cron-summary-chip ${state}`}><StatusIcon state={state} />{statusCounts[state]} {shortStatusLabels[state]}</span>)}</div>
          </div>
          <div className="cron-overview-card">
            <div className="cron-eyebrow">最近采样</div>
            <div className="cron-sample-time">{time(view.observed_at)}</div>
            <div className="cron-sample-hint"><Clock3 aria-hidden="true" />15 秒自动刷新</div>
          </div>
        </div>
        {view.queues && <div className="cron-queues"><div className="cron-queue"><div><strong>直播分析队列</strong><span>{queueSummary(view.queues.live_analysis.by_status.pending ?? 0, view.queues.live_analysis.oldest_pending_at, view.observed_at)}</span></div><b>{view.queues.live_analysis.by_status.pending ?? 0}</b></div><div className="cron-queue"><div><strong>复盘队列</strong><span>{queueSummary(view.queues.report_tasks.by_status.pending ?? 0, view.queues.report_tasks.oldest_pending_at, view.observed_at)}</span></div><b>{view.queues.report_tasks.by_status.pending ?? 0}</b></div></div>}
        <section className="cron-table-panel" aria-label="定时任务列表"><div className="cron-table-heading"><h2>任务状态</h2><small>共 {view.jobs.length} 项 · 按异常优先显示</small></div><div className="cron-table-scroll" data-testid="cron-table-scroll"><div className="cron-columns"><span>任务</span><span>状态</span><span>上次运行</span><span>耗时</span><span>连续失败</span><span>类型</span><span>最近错误</span><span /></div>{displayedJobs.map((job) => <button key={job.name} className="cron-job" onClick={() => { setSelected(job.name); onSelectJob?.(job.name); }}><span><span className="cron-job-name">{jobLabels[job.name] ?? job.name}</span><span className="cron-job-code">{job.name}</span></span><span className={`cron-status ${job.health.state}`}>{statusLabels[job.health.state]}</span><span>{time(job.last_started_at)}</span><span>{duration(job.last_duration_ms, job.kind)}</span><span>{job.consecutive_failures}</span><span>{interval(job)}</span><span className={`cron-error-summary ${job.last_error ? '' : 'muted'}`}>{job.last_error ?? '—'}</span><span className="cron-arrow">›</span></button>)}</div></section>
      </>}
    </div>
    {selectedJob && <>
      <div className="cron-backdrop" onClick={() => setSelected(null)} />
      <aside className="cron-history" aria-label="任务运行历史">
        <div className="cron-history-head">
          <div>
            <div className="cron-detail-kicker">任务详情 <span className={`cron-summary-chip ${view.state === 'api-error' ? 'pending' : selectedJob.health.state}`}><StatusIcon state={view.state === 'api-error' ? 'pending' : selectedJob.health.state} />{view.state === 'api-error' ? '待确认' : statusLabels[selectedJob.health.state]}</span></div>
            <h2>{jobLabels[selectedJob.name] ?? selectedJob.name}</h2>
            <code>{selectedJob.name}</code>
          </div>
          <button aria-label="关闭运行历史" onClick={() => setSelected(null)}>×</button>
        </div>
        <div className="cron-history-scroll" data-testid="cron-history-scroll">
          <p className="cron-detail-purpose">{jobDescriptions[selectedJob.name] ?? '此任务尚无用途说明，请参照任务 ID 和运行记录排查。'}</p>
          <div className="cron-detail-label">当前状态</div>
          <div className={`cron-detail-reason ${view.state === 'api-error' ? 'pending' : selectedJob.health.state}`}>
            <StatusIcon state={view.state === 'api-error' ? 'pending' : selectedJob.health.state} />
            <span>{view.state === 'api-error' ? `当前状态待确认；上次采样：${selectedJob.health.reason}` : selectedJob.health.reason}</span>
          </div>
          <div className="cron-detail-facts">
            <div><small>运行方式</small><strong>{cadence(selectedJob)}</strong></div>
            <div><small>上次运行</small><strong>{fullTime(selectedJob.last_started_at)}</strong></div>
            <div><small>上次成功</small><strong>{fullTime(selectedJob.last_success_at)}</strong></div>
            <div><small>{selectedJob.kind === 'loop' ? '正在处理' : '本次耗时'}</small><strong>{selectedJob.kind === 'loop' && selectedJob.loop_stats ? `${selectedJob.loop_stats.in_flight} / ${selectedJob.loop_stats.capacity}` : duration(selectedJob.last_duration_ms, selectedJob.kind)}</strong></div>
          </div>
          {selectedJob.last_error && <><div className="cron-detail-label">最近错误</div><div className="cron-detail-error">{selectedJob.last_error}</div></>}
          <section className="cron-detail-runs" aria-label="运行历史记录">
            <h3>运行历史</h3>
            <p className="cron-detail-runs-caption">最近 {runs.length} 条 · 单次最多显示 200 条</p>
            {view.historyLoading && <p role="status">正在读取运行历史…</p>}
            {view.historyError && <p role="alert">{view.historyError}</p>}
            {!view.historyLoading && !view.historyError && runs.length === 0 && <p>暂无运行记录。</p>}
            {runs.map((run) => <div className="cron-run" data-testid="cron-run" key={run.id}><div className="cron-run-head"><time>{runTime(run.started_at)}</time><span className={`cron-status ${run.status === 'success' ? 'ok' : run.status}`}>{runStatus(run)}</span></div><div className="cron-run-info">{run.error_count ? `${run.error_count} 条 ERROR · ` : ''}{duration(run.duration_ms, 'interval')}</div>{run.error && <div className="cron-run-error">{run.error}</div>}</div>)}
          </section>
        </div>
        <div className="cron-history-foot">仅显示最近记录 · 状态和错误均来自 cron 记录器</div>
      </aside>
    </>}
  </main>;
}
