import { ThemeProvider } from '@mui/material/styles';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { kioskTheme } from '../../theme';
import ReportImportMenu from './ReportImportMenu';

/**
 * 2026-08-22:触发器从 MUI 按钮换成了 `.kiosk-card` —— 屏 19「生成报告」那一组三张卡
 * 必须一样大(「同一屏上的卡不许有第二种尺寸」)。所以这里按可及名找它,
 * 而**卡本身 220×76 那条几何不在这儿断言**:那是 CSS 类给的,jsdom 看不见,
 * 判据在 `tests/kiosk-shell-geometry.spec.ts`。
 */

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
    const trigger = screen.getByRole('button', { name: /导入棋谱复盘/ });

    await user.click(trigger);
    await user.click(screen.getByRole('menuitem', { name: '从本地导入 SGF' }));
    expect(handlers.onImportLocal).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();

    await user.click(trigger);
    await user.click(screen.getByRole('menuitem', { name: '从棋谱库导入' }));
    expect(handlers.onImportLibrary).toHaveBeenCalledOnce();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
    expect(handlers.parentClick).not.toHaveBeenCalled();
  });

  it('clears the menu when dismissed and gives the menu rows 48px touch height', async () => {
    const user = userEvent.setup();
    renderMenu();
    const trigger = screen.getByRole('button', { name: /导入棋谱复盘/ });

    await user.click(trigger);
    for (const label of ['从本地导入 SGF', '从棋谱库导入']) {
      expect(screen.getByRole('menuitem', { name: label })).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    }
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
