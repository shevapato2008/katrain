import { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import AuthRequiredDialog from './AuthRequiredDialog';
vi.mock('../../../hooks/useTranslation', () => ({ useTranslation: () => ({ t: (_key: string, fallback: string) => fallback }) }));
const auth = vi.hoisted(() => ({ status: 'guest', isAuthenticated: false, retry: vi.fn() }));
vi.mock('../../../context/AuthContext', () => ({ useAuth: () => auth }));
vi.mock('./LoginModal', () => ({ default: ({ onClose }: { onClose: () => void }) => <button onClick={onClose}>Cancel login</button> }));
describe('protected action prompt', () => {
  beforeEach(() => { auth.status = 'guest'; auth.isAuthenticated = false; auth.retry.mockReset(); });
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
  it('closes after an unavailable/checking identity retry recovers without replaying the operation', async () => {
    const close = vi.fn();
    const recovered = vi.fn();
    const operation = vi.fn();
    const Owner = () => {
      const [open, setOpen] = useState(true);
      return <><button onClick={operation}>开始研究</button><AuthRequiredDialog open={open} onClose={close}
        onAuthenticated={() => { recovered(); setOpen(false); }} /></>;
    };
    auth.status = 'unavailable';
    const view = render(<Owner />);
    fireEvent.click(screen.getByRole('button', { name: '重试' }));
    expect(auth.retry).toHaveBeenCalledOnce();
    auth.status = 'checking';
    view.rerender(<Owner />);
    expect(recovered).not.toHaveBeenCalled();
    auth.status = 'authenticated';
    auth.isAuthenticated = true;
    view.rerender(<Owner />);
    expect(recovered).toHaveBeenCalledOnce();
    expect(close).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: '开始研究' })).toBeInTheDocument();
    expect(operation).not.toHaveBeenCalled();
  });

});
