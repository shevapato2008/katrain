import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { ReportTaskSummary } from '../../api/reportApi';
import { ReportProgressColumn } from './ReportProgressColumn';

const t = (_key: string, fallback?: string) => fallback ?? _key;
const task = (over: Partial<ReportTaskSummary> = {}): ReportTaskSummary => ({
  id: 1, user_game_id: 'game', report_type: 'normal', status: 'completed',
  total_moves: 120, analyzed_moves: 120, requested_visits: 500, started_at: null, completed_at: null, ...over,
});

describe('ReportProgressColumn', () => {
  it('renders completed normal and running advanced as separate noninteractive rows', () => {
    const { container } = render(<ReportProgressColumn surface="kiosk" moveCount={120} t={t} state={{
      completedNormal: task(), activeDeep: task({ id: 2, report_type: 'deep', status: 'running', analyzed_moves: 53 }),
    }} />);
    const bars = screen.getAllByRole('progressbar');
    expect(bars.map(bar => bar.getAttribute('aria-valuenow'))).toEqual(['100', '44']);
    expect(bars.map(bar => bar.tagName)).toEqual(['DIV', 'DIV']);
    expect(bars.every(bar => !bar.hasAttribute('tabindex'))).toBe(true);
    expect(bars[1]).toHaveTextContent('Advanced report44%');
    expect(bars[1].querySelector('.report-tier-fill')).toHaveStyle({ width: '44%' });
    expect(container.querySelector('button,svg')).toBeNull();
    expect(bars[0]).toHaveAttribute('data-status', 'completed');
    expect(bars[1]).toHaveAttribute('data-status', 'running');
  });

  it('uses the same value for Galaxy ring, percent and aria even while running at 100%', () => {
    render(<ReportProgressColumn surface="galaxy" moveCount={120} t={t} state={{
      activeNormal: task({ status: 'running' }), activeDeep: task({ report_type: 'deep', status: 'running', analyzed_moves: 60 }),
    }} />);
    const bars = screen.getAllByRole('progressbar');
    expect(bars[0]).toHaveAttribute('data-status', 'running');
    expect(bars[0]).toHaveAttribute('aria-valuenow', '100');
    expect(bars[1]).toHaveTextContent('50%');
    expect(bars[1].querySelector('.report-tier-ring-value')).toHaveAttribute('stroke-dasharray', '50 100');
  });
});
