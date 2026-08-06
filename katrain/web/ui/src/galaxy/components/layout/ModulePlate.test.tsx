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

  it('puts a named parent action to the right of the title when backLabel is provided', () => {
    const requestNavigation = vi.fn();
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation } as never);

    render(<ModulePlate title="升降级对弈" backLabel="升降级" backTo="/galaxy/play/ai?mode=rated" />);

    const plate = screen.getByTestId('module-plate');
    const heading = screen.getByRole('heading', { name: '升降级对弈' });
    const back = screen.getByRole('button', { name: '返回升降级' });
    expect(heading.compareDocumentPosition(back) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(plate).toHaveStyle({ justifyContent: 'space-between' });
    fireEvent.click(back);
    expect(requestNavigation).toHaveBeenCalledWith('/galaxy/play/ai?mode=rated');
  });
});
