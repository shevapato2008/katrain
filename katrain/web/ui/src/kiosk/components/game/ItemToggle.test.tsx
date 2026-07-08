import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../../theme';
import ItemToggle from './ItemToggle';

const renderToggle = (props: Partial<React.ComponentProps<typeof ItemToggle>> = {}) =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <ItemToggle icon={<span>i</span>} label="领地" onClick={vi.fn()} {...props} />
    </ThemeProvider>
  );

describe('ItemToggle badge', () => {
  it('renders no badge when badge prop is omitted', () => {
    renderToggle();
    expect(screen.queryByTestId('item-badge')).toBeNull();
  });

  it('renders the count when badge is a number', () => {
    renderToggle({ badge: 398 });
    expect(screen.getByTestId('item-badge').textContent).toBe('398');
  });

  it('renders 0 (次数不足) as "0", NOT "—"', () => {
    renderToggle({ badge: 0 });
    expect(screen.getByTestId('item-badge').textContent).toBe('0');
  });

  it('renders "—" (unknown), NOT "0", when badge is null', () => {
    renderToggle({ badge: null });
    const badge = screen.getByTestId('item-badge');
    expect(badge.textContent).toBe('—');
    expect(badge.textContent).not.toBe('0');
  });
});
