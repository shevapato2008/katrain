import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { OrientationProvider, useOrientation } from '../context/OrientationContext';

const STORAGE_KEY = 'katrain_kiosk_rotation';

// Mock localStorage (jsdom doesn't provide full implementation)
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

const TestConsumer = () => {
  const { rotation, setRotation } = useOrientation();
  return (
    <div>
      <span data-testid="rotation">{rotation}</span>
      <button onClick={() => setRotation(180)}>set-180</button>
      <button onClick={() => setRotation(0)}>set-0</button>
    </div>
  );
};

describe('OrientationContext', () => {
  beforeEach(() => { localStorage.clear(); });

  it('defaults to rotation 0', () => {
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });

  it('setRotation persists (use 180)', () => {
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    act(() => { screen.getByText('set-180').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('180');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('180');
  });

  it('ignores invalid → 0', () => {
    localStorage.setItem(STORAGE_KEY, '45');
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });

  it('migrates stale 90 to 0 and rewrites storage', () => {
    localStorage.setItem(STORAGE_KEY, '90');
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    expect(screen.getByTestId('rotation').textContent).toBe('0');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('0');
  });

  it('throws when used outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow();
    spy.mockRestore();
  });
});
