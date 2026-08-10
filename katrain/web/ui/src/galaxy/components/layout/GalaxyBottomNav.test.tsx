import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useGameNavigation } from '../../context/GameNavigationContext';
import GalaxyBottomNav from './GalaxyBottomNav';

vi.mock('../../context/GameNavigationContext', () => ({ useGameNavigation: vi.fn() }));
vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));

const RouteChange = () => {
  const navigate = useNavigate();
  return <button onClick={() => navigate('/galaxy/live')}>change route</button>;
};

describe('GalaxyBottomNav', () => {
  const requestNavigation = vi.fn();

  beforeEach(() => {
    requestNavigation.mockReset();
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation } as never);
  });

  it('fixes at most five direct destinations to the viewport and guards navigation', () => {
    render(<MemoryRouter><GalaxyBottomNav /></MemoryRouter>);

    const nav = screen.getByRole('navigation', { name: 'Primary navigation' });
    expect(nav).toHaveStyle({ position: 'fixed' });
    const directDestinations = screen.getAllByTestId('galaxy-bottom-destination');
    expect(directDestinations).toHaveLength(5);

    fireEvent.click(screen.getByRole('button', { name: 'Home' }));
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy');
  });

  it('puts every remaining destination in More and closes it on route change', async () => {
    render(<MemoryRouter><GalaxyBottomNav /><RouteChange /></MemoryRouter>);

    fireEvent.click(screen.getByRole('button', { name: 'More' }));
    for (const label of ['Live', 'Kifu', 'Tutorials']) {
      expect(screen.getByRole('menuitem', { name: label })).toBeInTheDocument();
    }

    fireEvent.click(screen.getByRole('button', { name: 'change route', hidden: true }));
    await waitFor(() => expect(screen.queryByRole('menuitem', { name: 'Live' })).not.toBeInTheDocument());
  });
});
