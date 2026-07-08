import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import Header from '../components/layout/Header';

const renderWithTheme = (ui: React.ReactElement) =>
  render(<ThemeProvider theme={kioskTheme}>{ui}</ThemeProvider>);

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
});
