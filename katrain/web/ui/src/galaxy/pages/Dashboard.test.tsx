import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Dashboard from './Dashboard';
import { GameNavigationProvider } from '../context/GameNavigationContext';

vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));

// 页头改用共享的 `ContentPageHeader`（spec §2.4：左上角箭头图标键 + 标题），它经由
// `ModulePlate` 读 `GameNavigationContext`。生产里 provider 挂在 `MainLayout` 上、
// 覆盖全部 galaxy 路由，所以这里补的是**测试的装配**，不是生产缺口。
describe('Dashboard module overview', () => {
  it('keeps rated-play details inside the Play module', () => {
    render(<MemoryRouter><GameNavigationProvider><Dashboard /></GameNavigationProvider></MemoryRouter>);
    expect(screen.queryByRole('heading', { name: 'AI升降级对弈' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Play' })).toBeInTheDocument();
  });
});
