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
  const { rotation, isPortrait, setRotation } = useOrientation();
  return (
    <div>
      <span data-testid="rotation">{rotation}</span>
      <span data-testid="is-portrait">{String(isPortrait)}</span>
      <button onClick={() => setRotation(90)}>set-90</button>
      <button onClick={() => setRotation(180)}>set-180</button>
      <button onClick={() => setRotation(0)}>set-0</button>
    </div>
  );
};

describe('OrientationContext', () => {
  beforeEach(() => { localStorage.clear(); });

  it('defaults to rotation 0 and landscape', () => {
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    expect(screen.getByTestId('rotation').textContent).toBe('0');
    expect(screen.getByTestId('is-portrait').textContent).toBe('false');
  });

  it('reads saved rotation from localStorage', () => {
    localStorage.setItem(STORAGE_KEY, '90');
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    expect(screen.getByTestId('rotation').textContent).toBe('90');
    expect(screen.getByTestId('is-portrait').textContent).toBe('true');
  });

  it('setRotation updates state and persists', () => {
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    act(() => { screen.getByText('set-90').click(); });
    expect(screen.getByTestId('rotation').textContent).toBe('90');
    expect(localStorage.getItem(STORAGE_KEY)).toBe('90');
  });

  it('isPortrait is false for 0 and 180', () => {
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    act(() => { screen.getByText('set-180').click(); });
    expect(screen.getByTestId('is-portrait').textContent).toBe('false');
  });

  it('ignores invalid localStorage value', () => {
    localStorage.setItem(STORAGE_KEY, '45');
    render(<OrientationProvider><TestConsumer /></OrientationProvider>);
    expect(screen.getByTestId('rotation').textContent).toBe('0');
  });

  it('throws when used outside provider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<TestConsumer />)).toThrow();
    spy.mockRestore();
  });
});
