import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { useGameNavigation } from '../../context/GameNavigationContext';
import ModulePlate from './ModulePlate';

vi.mock('../../context/GameNavigationContext', () => ({ useGameNavigation: vi.fn() }));
vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));

describe('ModulePlate', () => {
  it('renders its pure content and navigates back through the guarded flow', () => {
    const requestNavigation = vi.fn();
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation } as never);

    render(<ModulePlate title="Live match" subtitle="Round 3" status={<span>LIVE</span>} backTo="/galaxy/live" />);

    expect(screen.getByText('Live match')).toBeInTheDocument();
    expect(screen.getByText('Round 3')).toBeInTheDocument();
    expect(screen.getByText('LIVE')).toBeInTheDocument();
    const back = screen.getByRole('button', { name: 'Back' });
    expect(back).toHaveStyle({ width: '40px', height: '40px' });
    fireEvent.click(back);
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy/live');
  });

  it('renders no back control when showBack is false', () => {
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);
    render(<ModulePlate title="Research" backTo="/galaxy/research" showBack={false} />);
    expect(screen.queryByRole('button', { name: 'Back' })).not.toBeInTheDocument();
  });
});
