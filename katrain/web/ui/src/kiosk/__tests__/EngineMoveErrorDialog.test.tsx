import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import EngineMoveErrorDialog from '../components/physical/EngineMoveErrorDialog';
import { ApiError } from '../../api';

const retry = vi.fn();
const cancel = vi.fn();
// Mirrors the real api.ts's ApiError shape (status-carrying Error subclass) so the
// dialog's `err instanceof ApiError` check works against this mocked module too.
const { MockApiError } = vi.hoisted(() => ({
  MockApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.name = 'ApiError';
      this.status = status;
    }
  },
}));
vi.mock('../../api', () => ({
  API: {
    visionEngineMoveRetry: (...a: unknown[]) => retry(...a),
    visionEngineMoveCancel: (...a: unknown[]) => cancel(...a),
  },
  ApiError: MockApiError,
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
    // col=3,row=3 -> D4 (core/GTP frame, row 0 = bottom; same formula as the AI-move banner)
    expect(screen.getByText(/D4/)).toBeInTheDocument();
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
    retry.mockRejectedValueOnce(new ApiError(409, 'Request failed 409: stale'));
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(screen.queryByText('星阵连接出错')).toBeNull());
    expect(await screen.findByText('该恢复请求已过期')).toBeInTheDocument();
  });

  it('cancel 409 (stale token) closes the dialog and shows an expired notice', async () => {
    cancel.mockRejectedValueOnce(new ApiError(409, 'Request failed 409: stale'));
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('拿回棋子'));
    await waitFor(() => expect(screen.queryByText('星阵连接出错')).toBeNull());
    expect(await screen.findByText('该恢复请求已过期')).toBeInTheDocument();
  });

  // Finding 1 (HIGH): apiPost throws a plain (non-ApiError) Error for network blips and
  // 5xx transport failures — those must NOT be treated as an expired recovery token. The
  // dialog stays open, shows a transient inline notice, and keeps the SAME token so the
  // next retry re-uses it (the backend never rotated it — it never even saw the request).
  it('retry network failure (non-ApiError throw) keeps the dialog open with a transient error and reuses the same token', async () => {
    retry.mockRejectedValueOnce(new Error('Failed to fetch')).mockResolvedValueOnce({ ok: true });
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(retry).toHaveBeenCalledWith('s1', 'tok-1', undefined));
    expect(await screen.findByText('网络异常，请重试')).toBeInTheDocument();
    expect(screen.getByText('星阵连接出错')).toBeInTheDocument(); // dialog still open
    expect(screen.queryByText('该恢复请求已过期')).toBeNull(); // NOT treated as expired

    fireEvent.click(screen.getByText('重试'));
    await waitFor(() => expect(retry).toHaveBeenLastCalledWith('s1', 'tok-1', undefined)); // same token reused
    await waitFor(() => expect(screen.queryByText('星阵连接出错')).toBeNull()); // second attempt succeeds
  });

  it('retry 5xx failure (non-ApiError throw) keeps the dialog open and re-enables the buttons', async () => {
    retry.mockRejectedValueOnce(new Error('Request failed 500: boom'));
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('重试'));
    expect(await screen.findByText('网络异常，请重试')).toBeInTheDocument();
    const retryButton = screen.getByText('重试').closest('button');
    expect(retryButton).not.toBeDisabled();
    const cancelButton = screen.getByText('拿回棋子').closest('button');
    expect(cancelButton).not.toBeDisabled();
  });

  it('cancel network failure keeps the dialog in the error phase (not waiting) with a transient error', async () => {
    cancel.mockRejectedValueOnce(new Error('Failed to fetch'));
    render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('拿回棋子'));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith('s1', 'tok-1', undefined));
    expect(await screen.findByText('网络异常，请重试')).toBeInTheDocument();
    expect(screen.getByText('星阵连接出错')).toBeInTheDocument(); // still the error phase
    expect(screen.queryByText('等待拿回棋子')).toBeNull(); // never entered waiting
  });

  it('cancel switches to the waiting state, and the resolved broadcast (error -> null) closes it', async () => {
    cancel.mockResolvedValueOnce({ ok: true, awaiting_removal: true });
    const { rerender } = render(<EngineMoveErrorDialog {...base} error={baseError} />);

    fireEvent.click(screen.getByText('拿回棋子'));
    await waitFor(() => expect(cancel).toHaveBeenCalledWith('s1', 'tok-1', undefined));
    expect(await screen.findByText('等待拿回棋子')).toBeInTheDocument();
    expect(screen.getByText(/D4/)).toBeInTheDocument();

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

  // Finding 2 (HIGH): clicking 认输 only opens GamePage's confirm sub-dialog (via
  // onResign) — it must NOT dismiss this dialog itself. If the user cancels that confirm
  // (fat-finger on a 7" kiosk), this dialog needs to still be here with working buttons.
  // GamePage decides when to actually close it (on a confirmed resign) via `onDismiss`.
  it('clicking 认输 does not dismiss the dialog itself — it stays open (and functional) until GamePage says otherwise', () => {
    const onResign = vi.fn();
    render(<EngineMoveErrorDialog {...base} onResign={onResign} error={baseError} />);

    fireEvent.click(screen.getByText('认输'));
    expect(onResign).toHaveBeenCalledTimes(1);
    // Still open with the same error — same token still usable, buttons still enabled.
    expect(screen.getByText('星阵连接出错')).toBeInTheDocument();
    expect(screen.getByText('重试').closest('button')).not.toBeDisabled();
    expect(screen.getByText('拿回棋子').closest('button')).not.toBeDisabled();
    expect(screen.getByText('认输').closest('button')).not.toBeDisabled();
  });
});
