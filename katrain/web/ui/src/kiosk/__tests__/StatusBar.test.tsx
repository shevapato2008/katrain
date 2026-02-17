import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import StatusBar from '../components/layout/StatusBar';

const renderWithTheme = (ui: React.ReactElement) =>
  render(<ThemeProvider theme={kioskTheme}>{ui}</ThemeProvider>);

describe('StatusBar', () => {
  it('renders KaTrain branding', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByText('KaTrain')).toBeInTheDocument();
  });

  it('renders engine status indicator', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByTestId('engine-status')).toBeInTheDocument();
  });

  it('renders username', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByText('张三')).toBeInTheDocument();
  });

  it('renders current time', () => {
    renderWithTheme(<StatusBar username="张三" />);
    expect(screen.getByTestId('clock')).toBeInTheDocument();
  });
});
