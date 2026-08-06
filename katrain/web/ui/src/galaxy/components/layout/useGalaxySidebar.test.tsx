import { act, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { GALAXY_SIDEBAR_STORAGE_KEY, useGalaxySidebar } from './useGalaxySidebar';

const mediaQueries = new Set<MediaQueryList & { dispatch: () => void }>();

const installLocalStorage = () => {
  const values = new Map<string, string>();
  Object.defineProperty(window, 'localStorage', {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => values.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => values.set(key, value)),
      removeItem: vi.fn((key: string) => values.delete(key)),
      clear: vi.fn(() => values.clear()),
      key: vi.fn(() => null),
      get length() { return values.size; },
    },
  });
};

const queryMatches = (query: string) => {
  const min = /min-width:\s*(\d+)px/.exec(query)?.[1];
  const max = /max-width:\s*(\d+(?:\.\d+)?)px/.exec(query)?.[1];
  return (!min || window.innerWidth >= Number(min)) && (!max || window.innerWidth <= Number(max));
};

const installMatchMedia = () => {
  mediaQueries.clear();
  window.matchMedia = vi.fn((query: string) => {
    const listeners = new Set<(event: MediaQueryListEvent) => void>();
    const mediaQuery = {
      media: query,
      get matches() { return queryMatches(query); },
      onchange: null,
      addEventListener: (_event: string, listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
      removeEventListener: (_event: string, listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
      addListener: (listener: (event: MediaQueryListEvent) => void) => listeners.add(listener),
      removeListener: (listener: (event: MediaQueryListEvent) => void) => listeners.delete(listener),
      dispatchEvent: () => true,
      dispatch: () => listeners.forEach((listener) => listener({ matches: queryMatches(query), media: query } as MediaQueryListEvent)),
    } as MediaQueryList & { dispatch: () => void };
    mediaQueries.add(mediaQuery);
    return mediaQuery;
  });
};

const setViewport = (width: number) => {
  Object.defineProperty(window, 'innerWidth', { configurable: true, value: width });
  act(() => mediaQueries.forEach((query) => query.dispatch()));
};

const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter>{children}</MemoryRouter>;

const NavigationHarness = () => {
  const { dockedExpanded, dockedWidth, mode, overlayOpen, toggle, toggleButtonRef } = useGalaxySidebar();
  const navigate = useNavigate();
  return (
    <>
      <button ref={toggleButtonRef} onClick={toggle}>toggle</button>
      <button onClick={() => navigate('/galaxy/live')}>route</button>
      <button onClick={() => navigate(-1)}>back</button>
      <output>{JSON.stringify({ dockedExpanded, dockedWidth, mode, overlayOpen })}</output>
    </>
  );
};

describe('useGalaxySidebar', () => {
  beforeEach(() => {
    installLocalStorage();
    localStorage.clear();
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 1536 });
    installMatchMedia();
  });

  it('defaults wide and standard docked modes open without writing storage', () => {
    const setItem = vi.mocked(window.localStorage.setItem);
    const { result } = renderHook(() => useGalaxySidebar(), { wrapper });

    expect(result.current).toMatchObject({ mode: 'wide-docked', dockedWidth: 240, dockedExpanded: true });
    expect(setItem).not.toHaveBeenCalled();

    setViewport(1200);
    expect(result.current).toMatchObject({ mode: 'standard-docked', dockedWidth: 216, dockedExpanded: true });
    expect(setItem).not.toHaveBeenCalled();
  });

  it('persists only a docked user toggle and releases all sidebar width', () => {
    const { result } = renderHook(() => useGalaxySidebar(), { wrapper });

    act(() => result.current.toggle());

    expect(result.current).toMatchObject({ dockedExpanded: false, dockedWidth: 0 });
    expect(localStorage.getItem(GALAXY_SIDEBAR_STORAGE_KEY)).toBe('false');
  });

  it('starts narrow overlay closed without writing storage and never carries docked openness into it', () => {
    const setItem = vi.mocked(window.localStorage.setItem);
    const { result } = renderHook(() => useGalaxySidebar(), { wrapper });

    setViewport(1199);
    expect(result.current).toMatchObject({ mode: 'narrow-overlay', dockedWidth: 0, overlayOpen: false });
    expect(setItem).not.toHaveBeenCalled();
  });

  it('restores stored docked state after returning from the overlay breakpoint', () => {
    localStorage.setItem(GALAXY_SIDEBAR_STORAGE_KEY, 'false');
    setViewport(1199);
    const { result } = renderHook(() => useGalaxySidebar(), { wrapper });

    act(() => result.current.toggle());
    expect(result.current.overlayOpen).toBe(true);
    setViewport(1200);

    expect(result.current).toMatchObject({ mode: 'standard-docked', dockedExpanded: false, dockedWidth: 0, overlayOpen: false });
  });

  it('clears and unmounts navigation state on the 899px mobile boundary', () => {
    setViewport(1199);
    const { result } = renderHook(() => useGalaxySidebar(), { wrapper });
    act(() => result.current.toggle());

    setViewport(899);

    expect(result.current).toMatchObject({ mode: 'mobile', dockedWidth: 0, overlayOpen: false });
  });

  it('removes docked navigation and its toggle state when 1200px crosses directly to 899px', () => {
    setViewport(1200);
    const { result } = renderHook(() => useGalaxySidebar(), { wrapper });
    expect(result.current.mode).toBe('standard-docked');

    setViewport(899);

    expect(result.current).toMatchObject({ mode: 'mobile', dockedWidth: 0, overlayOpen: false });
  });

  it('closes temporary navigation on route change and returns focus to its trigger', async () => {
    setViewport(1199);
    window.requestAnimationFrame = vi.fn((callback: FrameRequestCallback) => { callback(0); return 1; });
    render(<MemoryRouter><NavigationHarness /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }));
    expect(screen.getByText(/"overlayOpen":true/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'route' }));

    await waitFor(() => expect(screen.getByText(/"overlayOpen":false/)).toBeInTheDocument());
    expect(screen.getByRole('button', { name: 'toggle' })).toHaveFocus();

    fireEvent.click(screen.getByRole('button', { name: 'back' }));
    expect(screen.getByText(/"overlayOpen":false/)).toBeInTheDocument();
  });

  it('keeps temporary navigation closed after leaving and returning to its breakpoint', () => {
    setViewport(1199);
    render(<MemoryRouter><NavigationHarness /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'toggle' }));
    expect(screen.getByText(/"overlayOpen":true/)).toBeInTheDocument();

    setViewport(899);
    expect(screen.getByText(/"mode":"mobile"/)).toHaveTextContent('"overlayOpen":false');
    setViewport(1199);

    expect(screen.getByText(/"mode":"narrow-overlay"/)).toHaveTextContent('"overlayOpen":false');
  });
});
