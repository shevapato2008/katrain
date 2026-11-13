import { presentReportTier, type ReportGameStatus } from './reportModel';
import './reportProgress.css';

type TFn = (key: string, fallback?: string) => string;

/** Display only. Creation, viewing and retry stay in each surface's report menu. */
export function ReportProgressColumn({ state, moveCount, surface, t }: {
  state: ReportGameStatus;
  moveCount: number;
  surface: 'kiosk' | 'galaxy';
  t: TFn;
}) {
  return <div className={`report-progress-column report-progress-column--${surface}`}>
    {(['normal', 'deep'] as const).map(tier => {
      const value = presentReportTier(state, tier, moveCount);
      const label = tier === 'normal' ? t('report:tier_normal', 'Normal report') : t('report:tier_deep', 'Advanced report');
      const status = value.status === 'pending' ? t('report:queuing', 'Queued')
        : value.status === 'running' ? t('report:generating', 'Generating')
          : value.status === 'failed' ? t('report:summary_failed', 'failed')
            : value.status === 'completed' ? t('report:summary_done', 'Completed') : t('review:tag_unanalyzed', 'Not analyzed');
      const percent = value.status === 'missing' ? '—' : `${value.percent}%`;
      return <div key={tier} className="report-tier-status" data-status={value.status} data-tier={tier}
        role="progressbar" aria-label={`${label} · ${status}`} aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={value.percent} aria-valuetext={`${status} · ${value.analyzed}/${value.total}`}
        title={`${label} · ${status} · ${value.analyzed}/${value.total}`}>
        {surface === 'kiosk' && <span aria-hidden="true" className="report-tier-fill" style={{ width: `${value.percent}%` }} />}
        <span className="report-tier-name">{label}</span>
        {surface === 'galaxy' ? <span className="report-tier-ring">
          <svg viewBox="0 0 36 36" aria-hidden="true">
            <circle className="report-tier-ring-track" cx="18" cy="18" r="15" />
            <circle className="report-tier-ring-value" cx="18" cy="18" r="15" pathLength={100}
              strokeDasharray={`${value.percent} 100`} transform="rotate(-90 18 18)" />
            {value.status === 'running' && <circle className="report-tier-ring-glow" r="1.2"
              cx={18 + 15 * Math.sin(value.percent / 100 * 2 * Math.PI)}
              cy={18 - 15 * Math.cos(value.percent / 100 * 2 * Math.PI)} />}
          </svg>
          <span className="report-tier-percent">{percent}</span>
        </span> : <span className="report-tier-percent">{percent}</span>}
      </div>;
    })}
  </div>;
}
