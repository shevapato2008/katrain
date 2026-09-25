import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import PerformanceFixture from './PerformanceFixture';

describe('isolated performance preview', () => {
  it('switches only the preview state and theme', async () => {
    const user = userEvent.setup();
    render(<PerformanceFixture />);
    expect(screen.getByRole('heading', { name: '尚未接入' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '已配置示意' }));
    expect(screen.getByRole('heading', { name: 'Netdata 面板已配置' })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '白天版本' }));
    expect(screen.getByTestId('performance-fixture')).toHaveAttribute('data-theme', 'light');
  });
});
