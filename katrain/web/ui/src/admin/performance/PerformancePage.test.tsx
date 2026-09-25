import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PerformancePage from './PerformancePage';

describe('performance monitoring fixture', () => {
  it('keeps an unverified environment unknown and disables the monitor link', () => {
    render(<PerformancePage previewState="unconnected" />);
    expect(screen.getByRole('heading', { name: '尚未接入' })).toBeInTheDocument();
    expect(screen.getByText('状态未知')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开监控面板' })).toBeDisabled();
    expect(screen.queryByText(/CPU.*%/)).not.toBeInTheDocument();
  });

  it('labels a configured preview as a design example without enabling a link', () => {
    render(<PerformancePage previewState="connected" />);
    expect(screen.getByRole('heading', { name: 'Netdata 面板已配置' })).toBeInTheDocument();
    expect(screen.getByText('设计示例 · 此处不代表真实服务在线')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '打开 Netdata 面板' })).toBeDisabled();
    expect(screen.queryByRole('link', { name: /Netdata/ })).not.toBeInTheDocument();
  });
});
