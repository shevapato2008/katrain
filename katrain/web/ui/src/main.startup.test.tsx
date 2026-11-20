import { cloneElement, useEffect, type ReactElement } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

const app = vi.hoisted(() => ({
  throws: false,
  unmounts: 0,
  tree: null as ReactElement<{ children: ReactElement<{ onRetry?: () => void }> }> | null,
}));

vi.mock('react-dom/client', () => ({
  createRoot: () => ({ render: (tree: typeof app.tree) => { app.tree = tree; } }),
}));
vi.mock('./AppRouter', () => ({
  default: function AppRouter() {
    useEffect(() => () => { app.unmounts += 1; }, []);
    if (app.throws) throw new Error('private account/token must not enter diagnostics');
    return <div>Current game</div>;
  },
}));
vi.mock('./hooks/useTranslation', () => ({
  useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }),
}));

beforeAll(async () => {
  document.body.innerHTML = '<div id="root"></div>';
  await import('./main');
});

beforeEach(() => {
  app.throws = false;
  app.unmounts = 0;
  sessionStorage.clear();
  vi.spyOn(console, 'error').mockImplementation(() => {});
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe('root startup containment', () => {
  it('shows a visible manual retry when the application throws during render', () => {
    app.throws = true;
    const reload = vi.fn();
    expect(() => render(cloneElement(app.tree!.props.children, { onRetry: reload }))).not.toThrow();

    expect(screen.getByRole('alert')).toHaveTextContent('页面暂时无法显示');
    expect(reload).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }));
    expect(reload).toHaveBeenCalledTimes(1);
    const records = JSON.parse(sessionStorage.getItem('katrain:startup-failures')!);
    expect(records).toHaveLength(1);
    expect(records[0].category).toBe('render');
    expect(JSON.stringify(records)).not.toContain('private');
  });

  it('shows a preload retry without reloading or unmounting the current application', () => {
    const reload = vi.fn();
    render(cloneElement(app.tree!.props.children, { onRetry: reload }));
    const unmountsBeforeFailure = app.unmounts;
    const failure = new CustomEvent('vite:preloadError', {
      cancelable: true,
      detail: { payload: new Error('https://example.test/chunk.js?token=private') },
    });

    act(() => { window.dispatchEvent(failure); });

    expect(failure.defaultPrevented).toBe(true);
    expect(screen.getByRole('alert')).toHaveTextContent('部分页面加载失败');
    expect(screen.getByText('Current game')).toBeVisible();
    expect(app.unmounts).toBe(unmountsBeforeFailure);
    expect(reload).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }));
    expect(reload).toHaveBeenCalledTimes(1);
    const records = JSON.parse(sessionStorage.getItem('katrain:startup-failures')!);
    expect(records).toHaveLength(1);
    expect(records[0].category).toBe('preload');
    expect(JSON.stringify(records)).not.toMatch(/private|https|token|payload/);
  });
});
