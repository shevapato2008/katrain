import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Dashboard from './Dashboard';

vi.mock('../../context/SettingsContext', () => ({ useSettings: () => ({}) }));

describe('Dashboard module overview', () => {
  it('keeps rated-play details inside the Play module', () => {
    render(<MemoryRouter><Dashboard /></MemoryRouter>);
    expect(screen.queryByRole('heading', { name: 'AI升降级对弈' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Play' })).toBeInTheDocument();
  });
});
