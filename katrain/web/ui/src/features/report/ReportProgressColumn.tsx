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
  const runningTiers = (['normal', 'deep'] as const)
    .map(tier => presentReportTier(state, tier, moveCount))
    .filter(value => value.status === 'running');
  if (runningTiers.length === 0) return null;

  return <div className={`report-progress-column report-progress-column--${surface}`}>
    {runningTiers.map(value => {
      const label = value.tier === 'normal' ? t('report:tier_normal', 'Normal report') : t('report:tier_deep', 'Advanced report');
      const status = t('report:generating', 'Generating');
      return <div key={value.tier} className="report-tier-status" data-status={value.status} data-tier={value.tier}
        role="progressbar" aria-label={`${label} · ${status}`} aria-valuemin={0} aria-valuemax={100}
        aria-valuenow={value.percent} aria-valuetext={`${status} · ${value.analyzed}/${value.total}`}
        title={`${label} · ${status} · ${value.analyzed}/${value.total}`}>
        <span aria-hidden="true" className="report-tier-fill" style={{ width: `${value.percent}%` }} />
        <span className="report-tier-name">{label}</span>
        <span className="report-tier-percent">{value.percent}%</span>
      </div>;
    })}
  </div>;
}
