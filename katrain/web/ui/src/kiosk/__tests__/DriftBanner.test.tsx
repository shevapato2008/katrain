import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { DriftBanner } from '../pages/BaipuSessionPage';
import type { BaipuGeometryCorrection } from '../../api/baipuApi';

const renderBanner = (correction: BaipuGeometryCorrection | null) =>
  render(<ThemeProvider theme={kioskTheme}><DriftBanner correction={correction} /></ThemeProvider>);

describe('DriftBanner', () => {
  it('renders nothing when correction is null', () => {
    renderBanner(null);
    expect(screen.queryByTestId('baipu-drift-banner')).toBeNull();
  });

  it('renders nothing when corrected with no drift over threshold', () => {
    renderBanner({ status: 'corrected', drift: { median_cells: 0.02, over_threshold: false } });
    expect(screen.queryByTestId('baipu-drift-banner')).toBeNull();
  });

  it('shows the corrected banner when drift exceeded the threshold', () => {
    renderBanner({ status: 'corrected', drift: { median_cells: 0.6, over_threshold: true } });
    expect(screen.getByTestId('baipu-drift-banner').getAttribute('data-drift-status')).toBe('corrected');
  });

  it('shows a warning banner when stale (reused last geometry)', () => {
    renderBanner({ status: 'stale', drift: { median_cells: 0.6, over_threshold: true } });
    expect(screen.getByTestId('baipu-drift-banner').getAttribute('data-drift-status')).toBe('stale');
  });

  it('shows a warning banner when frozen (never corrected)', () => {
    renderBanner({ status: 'frozen', drift: { median_cells: 0.0, over_threshold: false } });
    expect(screen.getByTestId('baipu-drift-banner').getAttribute('data-drift-status')).toBe('frozen');
  });

  it('renders nothing when fiducial mode is off', () => {
    renderBanner({ status: 'off' });
    expect(screen.queryByTestId('baipu-drift-banner')).toBeNull();
  });
});
