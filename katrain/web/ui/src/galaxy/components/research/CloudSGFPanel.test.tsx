import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CloudSGFPanel from './CloudSGFPanel';
import { vi, describe, it, expect, Mock } from 'vitest';
import { useAuth } from '../../context/AuthContext';

// Mock fetch
global.fetch = vi.fn();

// Mock useAuth
vi.mock('../../context/AuthContext', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useAuth: vi.fn(),
  };
});

describe('CloudSGFPanel', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    (useAuth as Mock).mockReturnValue({ token: 'mock-token' });
  });

  it('renders game list from API', async () => {
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ([
        { id: 1, result: 'B+R', game_type: 'free', started_at: '2023-01-01T08:00:00.000Z' }
      ]),
    });

    render(<CloudSGFPanel />);

    await waitFor(() => {
        expect(screen.getByText(/B\+R/)).toBeInTheDocument();
    });
  });

  it('saves game to cloud', async () => {
    // List fetch (initial)
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });
    // Save fetch
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 2 }),
    });
    // List fetch (refresh)
    (global.fetch as Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => [],
    });

    render(<CloudSGFPanel />);
    
    const saveBtn = screen.getByText(/Save to Cloud/i);
    fireEvent.click(saveBtn);

    await waitFor(() => {
        expect(global.fetch).toHaveBeenCalledWith(
            expect.stringContaining('/api/v1/games'),
            expect.objectContaining({ method: 'POST' })
        );
    });
  });
});
