import { ThemeProvider } from '@mui/material/styles';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { kioskTheme } from '../../theme';
import ReportLocalImportDialog from './ReportLocalImportDialog';

vi.mock('../../../hooks/useTranslation', () => ({
  useTranslation: () => ({ lang: 'zh-CN', t: (_key: string, fallback?: string) => fallback ?? _key }),
}));

const sgf = (size: 9 | 13 | 19 = 19) =>
  `(;FF[4]GM[1]SZ[${size}]RU[Chinese]KM[7.5]PB[黑棋]PW[白棋]BR[2D]WR[3D];B[aa];W[bb])`;

function renderDialog(options: { loading?: boolean; onSubmit?: ReturnType<typeof vi.fn>; open?: boolean } = {}) {
  const onClose = vi.fn();
  const onSubmit = options.onSubmit ?? vi.fn();
  const view = render(
    <ThemeProvider theme={kioskTheme}>
      <ReportLocalImportDialog open={options.open ?? true} loading={options.loading} onClose={onClose} onSubmit={onSubmit} />
    </ThemeProvider>,
  );
  return { ...view, onClose, onSubmit };
}

interface DeferredReader {
  result: string | ArrayBuffer | null;
  error: DOMException | null;
  onload: FileReader['onload'];
  onerror: FileReader['onerror'];
}

function installDeferredFileReaders(): DeferredReader[] {
  const readers: DeferredReader[] = [];
  class DeferredFileReader {
    result: string | ArrayBuffer | null = null;
    error: DOMException | null = null;
    onload: FileReader['onload'] = null;
    onerror: FileReader['onerror'] = null;
    readAsText() { readers.push(this); }
  }
  vi.stubGlobal('FileReader', DeferredFileReader as unknown as typeof FileReader);
  return readers;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('ReportLocalImportDialog parsing and submission', () => {
  it('disables all submit modes for missing or invalid SGF', async () => {
    const user = userEvent.setup();
    renderDialog();
    const paste = screen.getByRole('textbox', { name: 'SGF 内容' });
    for (const label of ['仅导入', '导入并生成普通复盘', '导入并生成深度复盘']) {
      expect(screen.getByRole('button', { name: label })).toBeDisabled();
    }
    await user.type(paste, '这不是 SGF');
    expect(screen.getByText('无法解析 SGF，请检查内容。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '仅导入' })).toBeDisabled();
  });

  it.each([
    ['a non-Go collection', '(;FF[4]GM[2]SZ[19];B[aa])'],
    ['an out-of-board move', '(;FF[4]GM[1]SZ[9];B[zz])'],
    ['a malformed property', '(;FF[4]GM[1]SZ[19];B[aa]BROKEN)'],
    ['a sequence after a child variation', '(;FF[4]GM[1]SZ[19];B[aa](;W[bb]);B[cc])'],
  ])('rejects %s', async (_caseName, content) => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole('textbox', { name: 'SGF 内容' }));
    await user.paste(content);
    expect(screen.getByText('无法解析 SGF，请检查内容。')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '仅导入' })).toBeDisabled();
  });

  it.each([
    '(;FF[4]GM[1]SZ[9];B[];W[tt])',
    '(;FF[4]GM[1]SZ[19]C[escaped \\] bracket];B[aa])',
    '(;FF[4]GM[1]SZ[13]AB[aa][mm]AW[bb];W[])',
    '(;FF[4]GM[1]SZ[19];B[aa];W[bb](;B[cc])(;B[dd]))',
  ])('accepts valid pass, escape, and setup syntax: %s', async (content) => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole('textbox', { name: 'SGF 内容' }));
    await user.paste(content);
    expect(screen.getByTestId('local-import-metadata')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '仅导入' })).toBeEnabled();
  });

  it.each([9, 13, 19] as const)('parses pasted %i×%i metadata', async (size) => {
    const user = userEvent.setup();
    renderDialog();
    await user.click(screen.getByRole('textbox', { name: 'SGF 内容' }));
    await user.paste(sgf(size));
    expect(screen.getByTestId('local-import-metadata')).toHaveTextContent(`${size} × ${size}`);
    expect(screen.getByTestId('local-import-metadata')).toHaveTextContent('Chinese');
    expect(screen.getByTestId('local-import-metadata')).toHaveTextContent('7.5');
    expect(screen.getByTestId('local-import-metadata')).toHaveTextContent('2 手');
  });

  it('reads a local file, derives its title, and submits import-only, normal, and deep payloads', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderDialog({ onSubmit });
    const file = new File([sgf(13)], '决赛.sgf', { type: 'application/x-go-sgf' });
    await user.upload(screen.getByLabelText('选择本地文件'), file);

    expect(screen.getByRole('textbox', { name: '标题（可选）' })).toHaveValue('决赛');
    await user.click(screen.getByRole('button', { name: '仅导入' }));
    await user.click(screen.getByRole('button', { name: '导入并生成普通复盘' }));
    await user.click(screen.getByRole('button', { name: '导入并生成深度复盘' }));

    const payload = {
      title: '决赛', sgfContent: sgf(13), boardSize: 13, rules: 'Chinese', komi: 7.5,
      moveCount: 2, playerBlack: '黑棋', playerWhite: '白棋', blackRank: '2D', whiteRank: '3D',
    };
    expect(onSubmit).toHaveBeenNthCalledWith(1, payload);
    expect(onSubmit).toHaveBeenNthCalledWith(2, payload, 'normal');
    expect(onSubmit).toHaveBeenNthCalledWith(3, payload, 'deep');
  });

  it('keeps the newest file when two reads complete out of order', async () => {
    const readers = installDeferredFileReaders();
    renderDialog();
    const input = screen.getByLabelText('选择本地文件');
    fireEvent.change(input, { target: { files: [new File(['a'], '旧棋谱.sgf')] } });
    fireEvent.change(input, { target: { files: [new File(['b'], '新棋谱.sgf')] } });

    await act(async () => {
      readers[1].result = sgf(13);
      readers[1].onload?.call(readers[1] as FileReader, new ProgressEvent('load'));
    });
    await act(async () => {
      readers[0].result = sgf(9);
      readers[0].onload?.call(readers[0] as FileReader, new ProgressEvent('load'));
    });

    expect(screen.getByRole('textbox', { name: '标题（可选）' })).toHaveValue('新棋谱');
    expect(screen.getByTestId('local-import-metadata')).toHaveTextContent('13 × 13');
  });

  it('locks submits for the newest read and a stale completion cannot unlock them', async () => {
    const user = userEvent.setup();
    const readers = installDeferredFileReaders();
    renderDialog();
    await user.click(screen.getByRole('textbox', { name: 'SGF 内容' }));
    await user.paste(sgf(9));
    expect(screen.getByRole('button', { name: '仅导入' })).toBeEnabled();

    const input = screen.getByLabelText('选择本地文件');
    fireEvent.change(input, { target: { files: [new File(['b'], '处理中 B.sgf')] } });
    expect(screen.getByRole('button', { name: '仅导入' })).toBeDisabled();
    expect(screen.getByRole('textbox', { name: '标题（可选）' })).toBeDisabled();
    expect(screen.getByRole('textbox', { name: 'SGF 内容' })).toBeDisabled();

    fireEvent.change(input, { target: { files: [new File(['c'], '处理中 C.sgf')] } });
    await act(async () => {
      readers[0].result = sgf(13);
      readers[0].onload?.call(readers[0] as FileReader, new ProgressEvent('load'));
    });
    expect(screen.getByRole('button', { name: '仅导入' })).toBeDisabled();

    await act(async () => {
      readers[1].result = sgf(19);
      readers[1].onload?.call(readers[1] as FileReader, new ProgressEvent('load'));
    });
    expect(screen.getByRole('button', { name: '仅导入' })).toBeEnabled();
    expect(screen.getByTestId('local-import-metadata')).toHaveTextContent('19 × 19');
  });

  it('shows a translated active read error and always resets the file input', async () => {
    const readers = installDeferredFileReaders();
    renderDialog();
    const input = screen.getByLabelText('选择本地文件');
    Object.defineProperty(input, 'value', { configurable: true, writable: true, value: 'selected.sgf' });
    fireEvent.change(input, { target: { files: [new File(['bad'], '失败.sgf')] } });
    await act(async () => {
      readers[0].error = new DOMException('read failed');
      readers[0].onerror?.call(readers[0] as FileReader, new ProgressEvent('error'));
    });
    expect(screen.getByRole('alert')).toHaveTextContent('读取文件失败，请重试。');
    expect(input).toHaveValue('');
  });

  it('ignores a file completion after close/reopen and after unmount', async () => {
    const readers = installDeferredFileReaders();
    const view = renderDialog();
    fireEvent.change(screen.getByLabelText('选择本地文件'), {
      target: { files: [new File(['old'], '关闭前.sgf')] },
    });
    view.rerender(
      <ThemeProvider theme={kioskTheme}>
        <ReportLocalImportDialog open={false} onClose={view.onClose} onSubmit={view.onSubmit} />
      </ThemeProvider>,
    );
    await act(async () => {
      readers[0].result = sgf(9);
      readers[0].onload?.call(readers[0] as FileReader, new ProgressEvent('load'));
    });
    view.rerender(
      <ThemeProvider theme={kioskTheme}>
        <ReportLocalImportDialog open onClose={view.onClose} onSubmit={view.onSubmit} />
      </ThemeProvider>,
    );
    expect(screen.getByRole('textbox', { name: '标题（可选）' })).toHaveValue('');

    fireEvent.change(screen.getByLabelText('选择本地文件'), {
      target: { files: [new File(['old'], '卸载前.sgf')] },
    });
    view.unmount();
    await act(async () => {
      readers[1].result = sgf(19);
      readers[1].onload?.call(readers[1] as FileReader, new ProgressEvent('load'));
    });
    await waitFor(() => expect(document.body).not.toHaveTextContent('卸载前'));
  });

  it('locks close and every input/action while loading', async () => {
    const { onClose } = renderDialog({ loading: true });
    expect(screen.getByRole('textbox', { name: '标题（可选）' })).toBeDisabled();
    expect(screen.getByRole('textbox', { name: 'SGF 内容' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '正在导入…' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(onClose).not.toHaveBeenCalled();
  });
});

describe('ReportLocalImportDialog 1024×600 layout', () => {
  it('bounds the paper below 600px, scrolls only content, fixes actions, wraps labels, and keeps targets 48px', () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1024 });
    Object.defineProperty(window, 'innerHeight', { configurable: true, value: 600 });
    renderDialog();

    const paper = screen.getByRole('dialog', { name: '导入本地 SGF' });
    const content = screen.getByTestId('report-local-import-content');
    const actions = screen.getByTestId('report-local-import-actions');
    expect(paper).toHaveStyle({
      width: 'calc(100vw - 24px)',
      maxWidth: '960px',
      height: 'calc(100dvh - 24px)',
      maxHeight: '576px',
      overflow: 'hidden',
    });
    expect(content).toHaveStyle({ minWidth: '0', minHeight: '0', overflowY: 'auto', overflowX: 'hidden' });
    expect(actions).toHaveStyle({
      flexShrink: '0',
      overflowX: 'hidden',
      gridTemplateColumns: 'repeat(4, minmax(0, 1fr))',
    });
    expect(screen.getByRole('button', { name: '选择本地文件' })).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    for (const control of [
      screen.getByRole('textbox', { name: '标题（可选）' }),
      screen.getByRole('textbox', { name: 'SGF 内容' }),
    ]) {
      expect(control).toHaveStyle({ minHeight: '48px', minWidth: '48px' });
    }
    for (const label of ['取消', '仅导入', '导入并生成普通复盘', '导入并生成深度复盘']) {
      const button = screen.getByRole('button', { name: label });
      expect(button).toHaveStyle({ minHeight: '48px', minWidth: '48px', whiteSpace: 'normal' });
    }
  });
});
