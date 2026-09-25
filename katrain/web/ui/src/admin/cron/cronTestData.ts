import type { CronHealth, CronJob, CronRun, CronView } from './types';

export const testStates = ['healthy', 'failed', 'offline', 'api-error', 'no-table', 'empty', 'loading', 'history', 'signin'] as const;
const day = '2026-09-24T';
const at = (time: string) => `${day}${time}+08:00`;
const jobs: Array<[string, string, number | null, string, number | null, string | null]> = [
  ['poll_moves', '落子轮询', 3, '16:32:05', 480, '15:43 落子轮询请求失败'],
  ['analyze', '直播分析', null, '16:31:48', null, '13:12 分析循环意外退出'],
  ['report_analyze', '复盘分析', null, '16:31:39', null, '12:51 复盘分析循环意外退出'],
  ['fetch_upcoming', '赛事预告', 900, '16:15:00', 1200, null],
  ['fetch_list', '赛事列表', 1800, '16:00:00', 2600, null],
  ['poll_pandanet', 'Pandanet 对局', 300, '16:30:00', 820, null],
  ['translate', '棋手译名', 3600, '15:00:00', 3800, null],
  ['tutorial_backup', '教程备份', 86400, '04:00:00', 12400, null],
  ['cleanup', '数据清理', 86400, '03:00:00', 4100, null],
];

function makeJob([name, , interval, time, duration, error]: typeof jobs[number]): CronJob {
  return {
    name, kind: interval === null ? 'loop' : 'interval', interval_seconds: interval, enabled: true,
    health: { state: 'ok', reason: '最近心跳和运行正常' },
    process_started_at: at('14:06:00'), heartbeat_at: at('16:32:00'),
    last_started_at: at(time), last_finished_at: at(time), last_success_at: at(time),
    last_status: 'success', last_duration_ms: duration, last_error: error,
    consecutive_failures: 0, loop_iteration_at: interval === null ? at(time) : null,
    loop_stats: interval === null ? { in_flight: 1, capacity: 2, errors_total: 0, last_error_at: null } : null,
  };
}

function makeRuns(job: CronJob, count: number, state: CronView['state']): CronRun[] {
  const step = job.interval_seconds && job.interval_seconds >= 60 ? job.interval_seconds * 1000 : 3600000;
  const base = new Date(job.last_started_at ?? at('16:00:00')).getTime();
  return Array.from({ length: count }, (_, index) => {
    const isBad = index === 0 && state === 'failed' && job.name === 'cleanup';
    const isError = index === 0 && state === 'failed' && job.name === 'fetch_list';
    const status: CronRun['status'] = isBad ? 'failed' : isError ? 'errors' : 'success';
    return { id: count - index, started_at: new Date(base - index * step).toISOString(), finished_at: new Date(base - index * step + 500).toISOString(), status,
      duration_ms: job.last_duration_ms ?? 198000, error_count: status === 'success' ? 0 : 1,
      error: isBad ? '清理任务连接数据库失败：连接超时' : isError ? '赛事列表接口响应超时' : null };
  });
}

export function testView(state: CronView['state']): CronView {
  const source = state === 'history' ? 'healthy' : state;
  const shownJobs = jobs.map(makeJob);
  if (source === 'failed') {
    const cleanup = shownJobs.find((job) => job.name === 'cleanup')!;
    cleanup.health = { state: 'failed', reason: '最近一次运行失败' }; cleanup.last_status = 'failed'; cleanup.consecutive_failures = 1; cleanup.last_error = '清理任务连接数据库失败';
    const list = shownJobs.find((job) => job.name === 'fetch_list')!;
    list.health = { state: 'errors', reason: '最近一次运行出现 ERROR' }; list.last_status = 'errors'; list.consecutive_failures = 1; list.last_error = '赛事列表接口响应超时';
  }
  if (source === 'offline') shownJobs.forEach((job) => { job.health = { state: 'offline', reason: '最后心跳超过 120 秒' }; job.heartbeat_at = at('16:29:54'); });
  const order: Record<CronHealth, number> = { failed: 0, errors: 1, offline: 0, stuck: 2, overdue: 3, running: 4, pending: 5, disabled: 6, ok: 7 };
  shownJobs.sort((a, b) => order[a.health.state] - order[b.health.state]);
  const runs = Object.fromEntries(shownJobs.map((job) => [job.name, makeRuns(job, ['analyze', 'report_analyze'].includes(job.name) ? 2 : job.name === 'poll_moves' ? 3 : ['cleanup', 'tutorial_backup'].includes(job.name) ? 14 : 200, source)]));
  return {
    state, observed_at: source === 'api-error' ? at('16:31:53') : at('16:32:08'),
    jobs: ['loading', 'no-table', 'empty', 'signin'].includes(state) ? [] : shownJobs, runs,
    queues: ['loading', 'no-table', 'empty', 'signin'].includes(state) ? null : {
      live_analysis: { by_status: { pending: 3 }, oldest_pending_at: at('16:30:08') },
      report_tasks: { by_status: { pending: 1 }, oldest_pending_at: at('16:31:30') },
    },
    error: source === 'api-error' ? '接口请求失败（503）' : undefined,
    selectedJob: state === 'history' ? 'fetch_upcoming' : undefined,
  };
}
