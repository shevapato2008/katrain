import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { ThemeProvider } from '@mui/material';
import { kioskTheme } from '../theme';
import { OrientationProvider, useOrientation } from '../context/OrientationContext';

// localStorage mock (jsdom doesn't provide full implementation)
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = String(value); },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

// Mock auth
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { id: 1, username: 'test', rank: '2D', credits: 0 },
    login: vi.fn(),
    logout: vi.fn(),
    token: 'mock-token',
  }),
}));

const STORAGE_KEY = 'katrain_kiosk_rotation';

/** Test consumer that reads and sets orientation */
const OrientationDisplay = () => {
  const { rotation, isPortrait, setRotation } = useOrientation();
  return (
    <div>
      <span data-testid="rotation">{rotation}</span>
      <span data-testid="is-portrait">{String(isPortrait)}</span>
      <button onClick={() => setRotation(0)}>set-0</button>
      <button onClick={() => setRotation(90)}>set-90</button>
      <button onClick={() => setRotation(180)}>set-180</button>
      <button onClick={() => setRotation(270)}>set-270</button>
    </div>
  );
};

const renderWithOrientation = () =>
  render(
    <ThemeProvider theme={kioskTheme}>
      <MemoryRouter>
        <OrientationProvider>
          <OrientationDisplay />
        </OrientationProvider>
      </MemoryRouter>
    </ThemeProvider>
  );

describe('Orientation integration', () => {
  beforeEach(() => {
    localStorageMock.clear();
  });

  it('defaults to rotation 0 (landscape)', () => {
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');
    expect(screen.getByTestId('is-portrait').textContent).toBe('false');
  });

  it('persisted 90 reads as portrait', () => {
    localStorageMock.setItem(STORAGE_KEY, '90');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('90');
    expect(screen.getByTestId('is-portrait').textContent).toBe('true');
  });

  it('persisted 180 reads as landscape (inverted)', () => {
    localStorageMock.setItem(STORAGE_KEY, '180');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('180');
    expect(screen.getByTestId('is-portrait').textContent).toBe('false');
  });

  it('persisted 270 reads as portrait (inverted)', () => {
    localStorageMock.setItem(STORAGE_KEY, '270');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('270');
    expect(screen.getByTestId('is-portrait').textContent).toBe('true');
  });

  it('setRotation updates state and persists to localStorage', () => {
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');

    act(() => { screen.getByText('set-90').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('90');
    expect(screen.getByTestId('is-portrait').textContent).toBe('true');
    expect(localStorageMock.getItem(STORAGE_KEY)).toBe('90');

    act(() => { screen.getByText('set-180').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('180');
    expect(screen.getByTestId('is-portrait').textContent).toBe('false');

    act(() => { screen.getByText('set-270').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('270');
    expect(screen.getByTestId('is-portrait').textContent).toBe('true');

    act(() => { screen.getByText('set-0').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('0');
    expect(screen.getByTestId('is-portrait').textContent).toBe('false');
  });

  it('ignores invalid localStorage value and defaults to 0', () => {
    localStorageMock.setItem(STORAGE_KEY, '45');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });
});
