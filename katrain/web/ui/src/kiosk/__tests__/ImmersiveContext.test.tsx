import { describe, it, expect, vi } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ImmersiveProvider, useImmersive } from '../context/ImmersiveContext';

const Probe = () => {
  const { immersive, setImmersive } = useImmersive();
  return (
    <div>
      <span data-testid="immersive">{String(immersive)}</span>
      <button onClick={() => setImmersive(true)}>on</button>
      <button onClick={() => setImmersive(false)}>off</button>
    </div>
  );
};

describe('ImmersiveContext', () => {
  it('defaults to non-immersive (false)', () => {
    render(<ImmersiveProvider><Probe /></ImmersiveProvider>);
    expect(screen.getByTestId('immersive').textContent).toBe('false');
  });

  it('setImmersive(true) then (false) flips and restores the flag', () => {
    render(<ImmersiveProvider><Probe /></ImmersiveProvider>);
    act(() => { screen.getByText('on').click(); });
    expect(screen.getByTestId('immersive').textContent).toBe('true');
    act(() => { screen.getByText('off').click(); });
    expect(screen.getByTestId('immersive').textContent).toBe('false');
  });

  it('throws when used outside an ImmersiveProvider', () => {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
    expect(() => render(<Probe />)).toThrow(/ImmersiveProvider/);
    spy.mockRestore();
  });
});
