import { ThemeProvider } from '@mui/material/styles';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { kioskTheme } from '../../theme';
import ReportImportMenu from './ReportImportMenu';

vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({
    lang: 'zh-CN',
    t: (_key: string, fallback?: string) => fallback ?? _key,
  }),
}));

function renderMenu(parentClick = vi.fn()) {
  const onImportLocal = vi.fn();
  const onImportLibrary = vi.fn();
  render(
    <ThemeProvider theme={kioskTheme}>
      <div onClick={parentClick}>
        <ReportImportMenu onImportLocal={onImportLocal} onImportLibrary={onImportLibrary} />
      </div>
    </ThemeProvider>,
  );
  return { onImportLocal, onImportLibrary, parentClick };
}

describe('ReportImportMenu', () => {
  it('opens each import flow, closes after choosing, and does not select a parent card', async () => {
    const user = userEvent.setup();
    const handlers = renderMenu();
    const trigger = screen.getByRole('button', { name: '导入棋谱' });

    await user.click(trigger);
    await user.click(screen.getByRole('menuitem', { name: '导入本地 SGF' }));
    expect(handlers.onImportLocal).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();

    await user.click(trigger);
    await user.click(screen.getByRole('menuitem', { name: '从棋谱库导入' }));
    expect(handlers.onImportLibrary).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(handlers.parentClick).not.toHaveBeenCalled();
  });

  it('clears the menu when dismissed and gives trigger and rows 48px touch height', async () => {
    const user = userEvent.setup();
    renderMenu();
    const trigger = screen.getByRole('button', { name: '导入棋谱' });
    expect(trigger).toHaveStyle({ minHeight: '48px', minWidth: '48px' });

    await user.click(trigger);
    for (const label of ['导入本地 SGF', '从棋谱库导入']) {
      expect(screen.getByRole('menuitem', { name: label })).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    }
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
