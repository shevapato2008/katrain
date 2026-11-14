import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReportTaskSummary } from '../../api/reportApi';
import { ReportProgressColumn } from './ReportProgressColumn';
import type { ReportGameStatus } from './reportModel';

const t = (_key: string, fallback?: string) => fallback ?? _key;
const task = (over: Partial<ReportTaskSummary> = {}): ReportTaskSummary => ({
  id: 1, user_game_id: 'game', report_type: 'normal', status: 'completed',
  total_moves: 120, analyzed_moves: 120, requested_visits: 500, started_at: null, completed_at: null, ...over,
});

const inactiveStates: [string, ReportGameStatus][] = [
  ['missing', {}],
  ['pending', { activeNormal: task({ status: 'pending' }), activeDeep: task({ report_type: 'deep', status: 'pending' }) }],
  ['failed', { failedNormal: task({ status: 'failed' }), failedDeep: task({ report_type: 'deep', status: 'failed' }) }],
  ['completed', { completedNormal: task(), completedDeep: task({ report_type: 'deep' }) }],
];

describe.each(['kiosk', 'galaxy'] as const)('ReportProgressColumn on %s', surface => {
  it.each(inactiveStates)('renders nothing when both tiers are %s', (_status, state) => {
    const { container } = render(<ReportProgressColumn surface={surface} moveCount={120} t={t} state={state} />);
    expect(screen.queryAllByRole('progressbar')).toHaveLength(0);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders only the running advanced tier beside a completed normal tier', () => {
    const { container } = render(<ReportProgressColumn surface={surface} moveCount={120} t={t} state={{
      completedNormal: task(), activeDeep: task({ id: 2, report_type: 'deep', status: 'running', analyzed_moves: 53 }),
    }} />);
    const bars = screen.getAllByRole('progressbar');
    expect(bars).toHaveLength(1);
    expect(bars[0]).toHaveAttribute('aria-valuenow', '44');
    expect(bars[0]).toHaveAttribute('aria-label', 'Advanced report · Generating');
    expect(bars[0]).toHaveAttribute('aria-valuetext', 'Generating · 53/120');
    expect(bars[0]).toHaveAttribute('title', 'Advanced report · Generating · 53/120');
    expect(bars[0].tagName).toBe('DIV');
    expect(bars[0]).not.toHaveAttribute('tabindex');
    expect(bars[0]).toHaveTextContent('Advanced report44%');
    expect(bars[0].querySelector('.report-tier-fill')).toHaveStyle({ width: '44%' });
    expect(container.querySelector('button,svg')).toBeNull();
    expect(container.querySelectorAll('.report-tier-status')).toHaveLength(1);
  });

  it('keeps both running tiers visible with charging fills, including at 100%, until completion', () => {
    const { container, rerender } = render(<ReportProgressColumn surface={surface} moveCount={120} t={t} state={{
      activeNormal: task({ status: 'running' }), activeDeep: task({ report_type: 'deep', status: 'running', analyzed_moves: 60 }),
    }} />);
    const bars = screen.getAllByRole('progressbar');
    expect(bars).toHaveLength(2);
    expect(bars[0]).toHaveAttribute('data-status', 'running');
    expect(bars[0]).toHaveAttribute('aria-valuenow', '100');
    expect(bars[0]).toHaveTextContent('Normal report100%');
    expect(bars[0].querySelector('.report-tier-fill')).toHaveStyle({ width: '100%' });
    expect(bars[1]).toHaveTextContent('Advanced report50%');
    expect(bars[1].querySelector('.report-tier-fill')).toHaveStyle({ width: '50%' });
    expect(container.querySelector('svg')).toBeNull();

    rerender(<ReportProgressColumn surface={surface} moveCount={120} t={t} state={{ completedNormal: task() }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
