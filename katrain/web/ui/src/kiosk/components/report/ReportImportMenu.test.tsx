import { ThemeProvider } from '@mui/material/styles';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { kioskTheme } from '../../theme';
import ReportImportMenu from './ReportImportMenu';

vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ lang: 'zh-CN', t: (_key: string, fallback?: string) => fallback ?? _key }),
}));

describe('ReportImportMenu', () => {
  it('opens the professional library on the first click without selecting a parent card', async () => {
    const onImportLibrary = vi.fn();
    const parentClick = vi.fn();
    render(<ThemeProvider theme={kioskTheme}>
      <div onClick={parentClick}><ReportImportMenu onImportLibrary={onImportLibrary} /></div>
    </ThemeProvider>);
    await userEvent.setup().click(screen.getByRole('button', { name: /导入棋谱复盘/ }));
    expect(onImportLibrary).toHaveBeenCalledOnce();
    expect(parentClick).not.toHaveBeenCalled();
    expect(screen.queryByRole('menu')).not.toBeInTheDocument();
  });
});
