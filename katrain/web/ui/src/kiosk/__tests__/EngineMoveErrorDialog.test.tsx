import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EngineMoveErrorDialog from '../components/physical/EngineMoveErrorDialog';

const retry = vi.fn();
const cancel = vi.fn();
vi.mock('../../api', () => ({
  API: {
    visionEngineMoveRetry: (...a: unknown[]) => retry(...a),
    visionEngineMoveCancel: (...a: unknown[]) => cancel(...a),
  },
}));

const baseError = { col: 3, row: 3, attempts: 3, detail: 'genmove timeout', recovery_token: 'tok-1' };
const base = { sessionId: 's1', boardSize: 19, onResign: vi.fn() };

describe('EngineMoveErrorDialog', () => {
  beforeEach(() => {
    retry.mockReset();
    cancel.mockReset();
  });

  it('renders nothing when error is null', () => {
    render(<EngineMoveErrorDialog {...base} error={null} />);
    expect(screen.queryByText('星阵连接出错')).toBeNull();
  });

  it('opens on a broadcast with the GTP coordinate + attempts rendered', () => {
    render(<EngineMoveErrorDialog {...base} error={baseError} />);
    expect(screen.getByText('星阵连接出错')).toBeInTheDocument();
    // col=3,row=3,boardSize=19 -> D16 (same formula as the AI-move banner)
    expect(screen.getByText(/D16/)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument(); // attempts
  });

  it('retry ok:false stays open, shows the new detail, and adopts the new token for the next retry', async () => {
    retry
      .mockResolvedValueOnce({ ok: false, detail: 'still failing', recovery_token: 'tok-2' })
      .mockResolvedValueOnce({ ok: true });
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(retry).toHaveBeenCalledWith('s1', 'tok-1', undefined));
    expect(await screen.findByText('still failing')).toBeInTheDocument();
    expect(screen.getByText('星阵连接出错')).toBeInTheDocument(); // still open

    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(retry).toHaveBeenLastCalledWith('s1', 'tok-2', undefined));
  });

  it('retry ok:true closes the dialog', async () => {
    retry.mockResolvedValueOnce({ ok: true });
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(screen.queryByText('星阵连接出错')).toBeNull());
  });

  it('retry 409 (stale token) closes the dialog and shows an expired notice', async () => {
    retry.mockRejectedValueOnce(new Error('Request failed 409: stale'));
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(screen.queryByText('星阵连接出错')).toBeNull());
    expect(await screen.findByText('该恢复请求已过期')).toBeInTheDocument();
  });

  it('cancel switches to the waiting state, and the resolved broadcast (error -> null) closes it', async () => {
    cancel.mockResolvedValueOnce({ ok: true, awaiting_removal: true });
    const { rerender } = render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('拿回棋子'));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith('s1', 'tok-1', undefined));
    expect(await screen.findByText('等待拿回棋子')).toBeInTheDocument();
    expect(screen.getByText(/D16/)).toBeInTheDocument();

    // Backend broadcasts physical_engine_error_resolved -> useGameSession nulls the error.
    rerender(<EngineMoveErrorDialog {...base} error={null} />);
    await waitFor(() => expect(screen.queryByText('等待拿回棋子')).toBeNull());
  });

  it('resign fires the existing resign-confirm flow', () => {
    const onResign = vi.fn();
    render(<EngineMoveErrorDialog {...base} onResign={onResign} error={baseError} />);

    fireEvent.click(screen.getByText('认输'));
    expect(onResign).toHaveBeenCalledTimes(1);
  });
});
