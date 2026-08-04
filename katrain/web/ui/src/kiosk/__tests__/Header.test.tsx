import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import Header from '../components/layout/Header';

const renderWithTheme = (ui: React.ReactElement) =>
  render(
    <MemoryRouter>
      <ThemeProvider theme={kioskTheme}>{ui}</ThemeProvider>
    </MemoryRouter>,
  );

const LocationProbe = () => {
  const location = useLocation();
  return (
    <output data-testid="location">
      {location.pathname}{location.search}|{String((location.state as { from?: string } | null)?.from ?? '')}
    </output>
  );
};

describe('Header', () => {
  it('renders 智星盒 brand name', () => {
    renderWithTheme(<Header username="张三" />);
    expect(screen.getByText('智星盒')).toBeInTheDocument();
  });

  it('renders StellaBox brand subtitle', () => {
    renderWithTheme(<Header username="张三" />);
    expect(screen.getByText('StellaBox')).toBeInTheDocument();
  });

  it('renders engine status indicator', () => {
    renderWithTheme(<Header username="张三" />);
    expect(screen.getByTestId('engine-status')).toBeInTheDocument();
  });

  it('renders username', () => {
    renderWithTheme(<Header username="张三" />);
    expect(screen.getByText('张三')).toBeInTheDocument();
  });

  it('renders current time', () => {
    renderWithTheme(<Header username="张三" />);
    expect(screen.getByTestId('clock')).toBeInTheDocument();
  });

  it('renders the native home action before identity when enabled', () => {
    const onHome = vi.fn();
    const { container } = renderWithTheme(<Header username="张三" showHome onHome={onHome} />);

    const home = screen.getByRole('button', { name: '返回智星盒主页' });
    expect(home).toHaveTextContent('主页');
    expect(home).toHaveStyle({ minWidth: '88px', minHeight: '48px', fontSize: '14px' });
    expect(home.compareDocumentPosition(screen.getByTestId('header-username')) & Node.DOCUMENT_POSITION_FOLLOWING)
      .toBeTruthy();

    fireEvent.click(home);
    expect(onHome).toHaveBeenCalledOnce();
    expect(container.querySelector('#smartbox-home-btn')).not.toBeInTheDocument();
  });

  it('uses a 56px header so the 48px home action is not clipped', () => {
    const { container } = renderWithTheme(<Header username="张三" showHome />);
    expect(container.querySelector('header')).toHaveStyle({ height: '56px' });
  });

  it('does not render the native home action when disabled', () => {
    renderWithTheme(<Header username="张三" showHome={false} />);
    expect(screen.queryByRole('button', { name: '返回智星盒主页' })).not.toBeInTheDocument();
  });

  it('renders a translated 48 by 48 Settings button', () => {
    renderWithTheme(<Header username="张三" />);

    const settings = screen.getByRole('button', { name: '设置' });
    expect(settings).toHaveStyle({ minWidth: '48px', width: '48px', minHeight: '48px', height: '48px' });
  });

  it('opens Settings with the current pathname and search in route state', () => {
    render(
      <MemoryRouter initialEntries={['/kiosk/kifu?page=2&q=%E6%A3%8B']}>
        <ThemeProvider theme={kioskTheme}>
          <Header username="张三" />
          <LocationProbe />
        </ThemeProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: '设置' }));

    expect(screen.getByTestId('location')).toHaveTextContent('/kiosk/settings|/kiosk/kifu?page=2&q=%E6%A3%8B');
  });
});
