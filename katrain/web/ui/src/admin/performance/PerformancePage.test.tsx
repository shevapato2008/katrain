import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PerformancePage from './PerformancePage';

describe('performance monitoring fixture', () => {
  it('keeps an unverified environment unknown without an embedded frame', () => {
    render(<PerformancePage previewState="unconnected" />);
    expect(screen.getByRole('heading', { name: '尚未接入' })).toBeInTheDocument();
    expect(screen.getByText('状态未知')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '内嵌监控看板' })).toBeInTheDocument();
    expect(screen.queryByTitle(/Grafana/)).not.toBeInTheDocument();
    expect(screen.queryByText(/CPU.*%/)).not.toBeInTheDocument();
  });

  it('labels the Grafana layout as a non-live design preview', () => {
    render(<PerformancePage previewState="connected" />);
    expect(screen.getByRole('heading', { name: '嵌入布局预览' })).toBeInTheDocument();
    expect(screen.getByText('设计示例 · 不是实时画面，也不代表服务在线')).toBeInTheDocument();
    expect(screen.getByLabelText('Grafana 嵌入布局设计示意；无实时数据')).toBeInTheDocument();
    expect(screen.getAllByText('暂无实时数据 · 设计占位')).toHaveLength(4);
    expect(screen.queryByTitle(/Grafana/)).not.toBeInTheDocument();
  });
});
