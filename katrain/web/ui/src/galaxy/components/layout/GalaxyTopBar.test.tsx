import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import GalaxyTopBar from './GalaxyTopBar';
import { useGameNavigation } from '../../context/GameNavigationContext';

vi.mock('../../context/GameNavigationContext', () => ({
  useGameNavigation: vi.fn(),
}));

describe('GalaxyTopBar', () => {
  it('renders the compact StellaBox brand lockup in the required order', () => {
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);

    render(<GalaxyTopBar />);

    const banner = screen.getByRole('banner');
    expect(banner).toHaveStyle({ height: '52px' });

    const home = screen.getByRole('button', { name: '回到首页' });
    const logo = screen.getByAltText('智星盒 StellaBox');
    const chineseBrand = screen.getByText('智星盒');
    const latinBrand = screen.getByText('StellaBox');

    expect(logo).toHaveAttribute('src', '/assets/img/logo-white.png');
    expect(chineseBrand).toHaveClass('galaxy-brand-cn');
    expect(latinBrand).not.toHaveClass('galaxy-brand-cn');
    expect(Array.from(home.children)).toEqual([logo, chineseBrand, latinBrand]);
  });

  it('returns home through the guarded Galaxy navigation flow', () => {
    const requestNavigation = vi.fn();
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation } as never);

    render(<GalaxyTopBar />);
    fireEvent.click(screen.getByRole('button', { name: '回到首页' }));

    expect(requestNavigation).toHaveBeenCalledWith('/galaxy');
  });

  it('accepts a right slot for global controls', () => {
    vi.mocked(useGameNavigation).mockReturnValue({ requestNavigation: vi.fn() } as never);

    render(<GalaxyTopBar rightSlot={<span>语言</span>} />);

    expect(screen.getByText('语言')).toBeInTheDocument();
  });
});
