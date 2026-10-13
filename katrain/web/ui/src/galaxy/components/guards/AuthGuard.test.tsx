import { useEffect } from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthGuard } from './AuthGuard';

const auth = vi.hoisted(() => ({ current: {} as any, retry: vi.fn(), mount: vi.fn(), cleanup: vi.fn() }));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => auth.current }));
vi.mock('../auth/LoginModal', () => ({ default: ({ onClose }: { onClose: () => void }) => <button onClick={onClose}>Cancel login</button> }));
const Protected = () => {
  useEffect(() => { auth.mount(); return auth.cleanup; }, []);
  return <div>PRIVATE CONTENT</div>;
};
const Tree = () => <MemoryRouter initialEntries={['/galaxy/play/human']}><Routes>
  <Route path="/galaxy/play/human" element={<AuthGuard feature="hall"><Protected /></AuthGuard>} />
  <Route path="/galaxy/play" element={<div>PUBLIC PLAY</div>} />
</Routes></MemoryRouter>;

describe('Galaxy page access', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    auth.current = { status: 'guest', isAuthenticated: false, isLoading: false, isGuest: false, user: null, identityKey: null, retry: auth.retry };
  });
  it.each(['guest', 'checking', 'unavailable', 'expired'])('does not mount protected children in %s', (status) => {
    auth.current.status = status;
    auth.current.isLoading = status === 'checking';
    render(<Tree />);
    expect(auth.mount).not.toHaveBeenCalled();
    expect(screen.queryByText('PRIVATE CONTENT')).not.toBeInTheDocument();
    expect(screen.getByTestId('protected-outline')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });
  it('opens existing login and returns to the gate when cancelled', () => {
    render(<Tree />);
    fireEvent.click(screen.getByRole('button', { name: '登录并继续' }));
    fireEvent.click(screen.getByText('Cancel login'));
    expect(screen.getByRole('dialog', { name: '登录后进入对战大厅' })).toBeInTheDocument();
    expect(auth.mount).not.toHaveBeenCalled();
  });
  it('retries unavailable identity and Escape returns to public play', () => {
    auth.current.status = 'unavailable';
    render(<Tree />);
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(auth.retry).toHaveBeenCalledOnce();
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape', code: 'Escape' });
    expect(screen.getByText('PUBLIC PLAY')).toBeInTheDocument();
  });
  it('unmounts on logout and remounts on account change', () => {
    auth.current = { ...auth.current, status: 'authenticated', isAuthenticated: true, user: { id: 1 }, identityKey: 'one' };
    const { rerender } = render(<Tree />);
    expect(auth.mount).toHaveBeenCalledTimes(1);
    auth.current = { ...auth.current, user: { id: 2 }, identityKey: 'two' };
    rerender(<Tree />);
    expect(auth.cleanup).toHaveBeenCalledTimes(1);
    expect(auth.mount).toHaveBeenCalledTimes(2);
    auth.current = { ...auth.current, status: 'guest', isAuthenticated: false, user: null, identityKey: null };
    act(() => { rerender(<Tree />); });
    expect(auth.cleanup).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('PRIVATE CONTENT')).not.toBeInTheDocument();
  });
  it('rejects the technical guest for real account pages', () => {
    auth.current = { ...auth.current, isAuthenticated: true, isGuest: true, user: { id: 0, username: 'guest' } };
    render(<Tree />);
    expect(auth.mount).not.toHaveBeenCalled();
  });
});
