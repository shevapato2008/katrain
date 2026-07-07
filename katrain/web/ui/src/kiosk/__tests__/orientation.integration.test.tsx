import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
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
  const { rotation, setRotation } = useOrientation();
  return (
    <div>
      <span data-testid="rotation">{rotation}</span>
      <button onClick={() => setRotation(0)}>set-0</button>
      <button onClick={() => setRotation(180)}>set-180</button>
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

  it('defaults to rotation 0', () => {
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });

  it('persisted 90 migrates and reads back as 0 (kiosk is landscape-only)', () => {
    localStorageMock.setItem(STORAGE_KEY, '90');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });

  it('persisted 180 reads as 180 (inverted landscape)', () => {
    localStorageMock.setItem(STORAGE_KEY, '180');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('180');
  });

  it('persisted 270 migrates and reads back as 0 (kiosk is landscape-only)', () => {
    localStorageMock.setItem(STORAGE_KEY, '270');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });

  it('setRotation updates state and persists to localStorage (0 ↔ 180 round-trip)', () => {
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');

    act(() => { screen.getByText('set-180').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('180');
    expect(localStorageMock.getItem(STORAGE_KEY)).toBe('180');

    act(() => { screen.getByText('set-0').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('0');
    expect(localStorageMock.getItem(STORAGE_KEY)).toBe('0');
  });

  it('ignores invalid localStorage value and defaults to 0', () => {
    localStorageMock.setItem(STORAGE_KEY, '45');
    renderWithOrientation();
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });
});
