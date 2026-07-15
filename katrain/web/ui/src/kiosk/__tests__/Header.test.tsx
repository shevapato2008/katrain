import { describe, it, expect } from 'vitest';
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
