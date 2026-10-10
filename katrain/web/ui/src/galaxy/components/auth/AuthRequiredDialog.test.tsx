import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AuthRequiredDialog from './AuthRequiredDialog';
vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => ({ status: 'guest', isAuthenticated: false, retry: vi.fn() }) }));
vi.mock('./LoginModal', () => ({ default: ({ onClose }: { onClose: () => void }) => <button onClick={onClose}>Cancel login</button> }));
describe('protected action prompt', () => {
  it('uses approved guidance and cancelling login preserves the action context', () => {
    const close = vi.fn();
    render(<AuthRequiredDialog open onClose={close} message="登录后可保存棋谱。" />);
    expect(screen.getByRole('button', { name: '继续浏览' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '登录并继续' }));
    fireEvent.click(screen.getByText('Cancel login'));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(close).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '继续浏览' }));
    expect(close).toHaveBeenCalledOnce();
  });
});
