import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
vi.mock('../../api', () => ({ API: { platformStatus: vi.fn().mockResolvedValue({ platforms: [] }) } }));
vi.mock('../../context/AuthContext', () => ({ useAuth: () => ({ token: 't' }) }));
import PlatformConnectPage from './PlatformConnectPage';

test('cross-platform page has a back bar (not a dead-end without the Dock)', async () => {
  render(<MemoryRouter><PlatformConnectPage /></MemoryRouter>);
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /返回|back/i })).toBeInTheDocument());
});
