import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, screen } from '@testing-library/react';
import GeometryVideoPanel from '../components/vision/GeometryVideoPanel';

const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
};
const bitmap = (width = 640, height = 480) => ({ width, height, close: vi.fn() }) as unknown as ImageBitmap;
const response = (status = 200) => new Response(status === 200 ? new Uint8Array([1]) : null, { status });
const fetchSnapshot = vi.fn<typeof fetch>();
const decodeBitmap = vi.fn<typeof createImageBitmap>();
const drawImage = vi.fn();
const onImageLoad = vi.fn();
const panel = (src = '/snapshot/raw') => (
  <GeometryVideoPanel
    snapshot src={src} alt="摄像头画面" onImageLoad={onImageLoad}
    overlay={<span>棋盘几何叠加层</span>}
  />
);
const flush = async () => { await act(async () => { await Promise.resolve(); }); };
const advance = async (ms: number) => {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
};

describe('GeometryVideoPanel snapshot recovery', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'performance'] });
    fetchSnapshot.mockReset().mockImplementation(async () => response());
    decodeBitmap.mockReset().mockImplementation(async () => bitmap());
    drawImage.mockReset();
    onImageLoad.mockReset();
    vi.stubGlobal('fetch', fetchSnapshot);
    vi.stubGlobal('createImageBitmap', decodeBitmap);
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext')
      .mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D);
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('retains the last frame with a reconnect warning after 503, hides its overlay, and recovers', async () => {
    const firstFrame = bitmap();
    const recoveredFrame = bitmap(800, 600);
    fetchSnapshot.mockResolvedValueOnce(response()).mockResolvedValueOnce(response(503));
    decodeBitmap.mockResolvedValueOnce(firstFrame).mockResolvedValueOnce(recoveredFrame);
    const { container } = render(panel());
    const canvas = container.querySelector('canvas')!;
    expect(screen.getByText('画面连接中…')).toBeInTheDocument();
    await flush();
    expect(canvas).toHaveStyle({ display: 'block' });
    expect(screen.getByText('棋盘几何叠加层')).toBeInTheDocument();

    await advance(200);
    expect(canvas).toHaveStyle({ display: 'block' });
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
    expect(screen.getByText('画面重连中…')).toBeInTheDocument();
    await advance(999);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
    await advance(1);
    expect(canvas).toHaveStyle({ display: 'block' });
    expect(screen.getByText('棋盘几何叠加层')).toBeInTheDocument();
    expect(screen.queryByText('画面重连中…')).toBeNull();
    expect(onImageLoad).toHaveBeenLastCalledWith({ width: 800, height: 600 });
    expect(firstFrame.close).toHaveBeenCalledTimes(1);
    expect(recoveredFrame.close).toHaveBeenCalledTimes(1);
    await advance(199);
    expect(fetchSnapshot).toHaveBeenCalledTimes(3);
    await advance(1);
    expect(fetchSnapshot).toHaveBeenCalledTimes(4);
  });

  it('expires the retained frame 3000 ms after its draw without extending it for repeated failures', async () => {
    fetchSnapshot.mockResolvedValue(response(503)).mockResolvedValueOnce(response());
    const { container } = render(panel());
    const canvas = container.querySelector('canvas')!;
    await flush();
    await advance(200);
    expect(canvas).toHaveStyle({ display: 'block' });
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
    await advance(2799);
    expect(fetchSnapshot).toHaveBeenCalledTimes(4);
    expect(canvas).toHaveStyle({ display: 'block' });
    await advance(1);
    expect(canvas).toHaveStyle({ display: 'none' });
    expect(screen.getByText('画面重连中…')).toBeInTheDocument();
  });

  it.each(['fetch', 'decode'] as const)('expires a frame while the next %s is still pending', async (phase) => {
    const pendingFetch = deferred<Response>();
    const pendingDecode = deferred<ImageBitmap>();
    fetchSnapshot.mockResolvedValueOnce(response()).mockReturnValue(pendingFetch.promise);
    if (phase === 'decode') fetchSnapshot.mockResolvedValueOnce(response());
    decodeBitmap.mockResolvedValueOnce(bitmap()).mockReturnValue(pendingDecode.promise);
    const { container } = render(panel());
    const canvas = container.querySelector('canvas')!;
    await flush();
    await advance(200);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
    await advance(2799);
    expect(canvas).toHaveStyle({ display: 'block' });
    await advance(1);
    expect(canvas).toHaveStyle({ display: 'none' });
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
    expect(screen.getByText('画面重连中…')).toBeInTheDocument();
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);

    if (phase === 'decode') {
      const freshFrame = bitmap(800, 600);
      await act(async () => { pendingDecode.resolve(freshFrame); });
      expect(canvas).toHaveStyle({ display: 'block' });
      expect(screen.getByText('棋盘几何叠加层')).toBeInTheDocument();
      expect(screen.queryByText('画面重连中…')).toBeNull();
      expect(freshFrame.close).toHaveBeenCalledTimes(1);
      await advance(2999);
      expect(canvas).toHaveStyle({ display: 'block' });
      await advance(1);
      expect(canvas).toHaveStyle({ display: 'none' });
    }
  });

  it('allows a 1601 ms bitmap decode after the complete body arrives without transport abort', async () => {
    const pendingDecode = deferred<ImageBitmap>();
    const frame = bitmap();
    decodeBitmap.mockReturnValueOnce(pendingDecode.promise);
    const { container } = render(panel());
    await flush();
    const signal = fetchSnapshot.mock.calls[0][1]!.signal!;
    await advance(1601);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    expect(signal.aborted).toBe(false);
    await act(async () => { pendingDecode.resolve(frame); });
    expect(container.querySelector('canvas')).toHaveStyle({ display: 'block' });
    expect(screen.getByText('棋盘几何叠加层')).toBeInTheDocument();
    expect(drawImage).toHaveBeenCalledWith(frame, 0, 0);
    expect(frame.close).toHaveBeenCalledTimes(1);
  });

  it('aborts a body still downloading at 1500 ms and does not decode its late result', async () => {
    const pendingBody = deferred<Blob>();
    const downloading = response();
    vi.spyOn(downloading, 'blob').mockReturnValueOnce(pendingBody.promise);
    fetchSnapshot.mockResolvedValueOnce(downloading);
    const { container } = render(panel());
    await flush();
    const signal = fetchSnapshot.mock.calls[0][1]!.signal!;
    await advance(1499);
    expect(signal.aborted).toBe(false);
    await advance(1);
    expect(signal.aborted).toBe(true);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    await act(async () => { pendingBody.resolve(new Blob([new Uint8Array([1])])); });
    expect(decodeBitmap).not.toHaveBeenCalled();
    expect(container.querySelector('canvas')).toHaveStyle({ display: 'none' });
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
    await advance(999);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
  });

  it('retries unavailable snapshots once per second without a tight error loop', async () => {
    fetchSnapshot.mockResolvedValue(response(503));
    const { container } = render(panel());
    await flush();
    await advance(999);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
    await advance(4000);
    expect(fetchSnapshot).toHaveBeenCalledTimes(6);
    expect(decodeBitmap).not.toHaveBeenCalled();
    expect(container.querySelector('canvas')).toHaveStyle({ display: 'none' });
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
    expect(screen.getByText('画面重连中…')).toBeInTheDocument();
  });

  it('keeps one request in flight and rejects a response arriving after the 1500 ms abort', async () => {
    const pending = deferred<Response>();
    fetchSnapshot.mockReturnValueOnce(pending.promise);
    const { container } = render(panel());
    const signal = fetchSnapshot.mock.calls[0][1]!.signal!;
    await advance(1499);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    expect(signal.aborted).toBe(false);
    await advance(1);
    expect(signal.aborted).toBe(true);
    await advance(500);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    await act(async () => { pending.resolve(response()); });
    expect(container.querySelector('canvas')).toHaveStyle({ display: 'none' });
    expect(drawImage).not.toHaveBeenCalled();
    expect(onImageLoad).not.toHaveBeenCalled();
    await advance(999);
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
  });

  it.each(['/snapshot/warped', '/snapshot/raw?revision=2'])('aborts the previous source and closes its late bitmap after switching to %s', async (nextSource) => {
    const oldDecode = deferred<ImageBitmap>();
    const oldFrame = bitmap(320, 240);
    const newFrame = bitmap(800, 600);
    decodeBitmap.mockReturnValueOnce(oldDecode.promise).mockResolvedValueOnce(newFrame);
    const { container, rerender } = render(panel());
    await flush();
    const oldSignal = fetchSnapshot.mock.calls[0][1]!.signal!;
    rerender(panel(nextSource));
    await flush();
    expect(oldSignal.aborted).toBe(true);
    expect(container.querySelector('canvas')).toHaveAttribute('data-src', nextSource);
    await act(async () => { oldDecode.resolve(oldFrame); });
    expect(drawImage).toHaveBeenCalledTimes(1);
    expect(drawImage).toHaveBeenLastCalledWith(newFrame, 0, 0);
    expect(onImageLoad).toHaveBeenCalledTimes(1);
    expect(oldFrame.close).toHaveBeenCalledTimes(1);
    expect(newFrame.close).toHaveBeenCalledTimes(1);
  });

  it('aborts on unmount and closes a bitmap decoded afterward without publishing it', async () => {
    const pendingDecode = deferred<ImageBitmap>();
    const lateFrame = bitmap();
    decodeBitmap.mockResolvedValueOnce(bitmap()).mockReturnValueOnce(pendingDecode.promise);
    const { unmount } = render(panel());
    await flush();
    await advance(200);
    const signal = fetchSnapshot.mock.calls[1][1]!.signal!;
    unmount();
    expect(signal.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    await act(async () => { pendingDecode.resolve(lateFrame); });
    expect(drawImage).toHaveBeenCalledTimes(1);
    expect(onImageLoad).toHaveBeenCalledTimes(1);
    expect(lateFrame.close).toHaveBeenCalledTimes(1);
    await advance(5000);
    expect(fetchSnapshot).toHaveBeenCalledTimes(2);
  });

  it.each(['missing source', 'snapshot disabled'] as const)('clears old frame state and timers when %s, including after reenabling', async (mode) => {
    const pendingDecode = deferred<ImageBitmap>();
    const pendingFetch = deferred<Response>();
    const lateFrame = bitmap();
    decodeBitmap.mockResolvedValueOnce(bitmap()).mockReturnValueOnce(pendingDecode.promise);
    const { container, rerender } = render(panel());
    await flush();
    await advance(200);
    const oldSignal = fetchSnapshot.mock.calls[1][1]!.signal!;
    rerender(
      <GeometryVideoPanel
        snapshot={mode !== 'snapshot disabled'} src={mode === 'missing source' ? undefined : '/snapshot/raw'}
        alt="摄像头画面" onImageLoad={onImageLoad}
      />,
    );
    expect(oldSignal.aborted).toBe(true);
    expect(vi.getTimerCount()).toBe(0);
    await act(async () => { pendingDecode.resolve(lateFrame); });
    expect(lateFrame.close).toHaveBeenCalledTimes(1);
    expect(drawImage).toHaveBeenCalledTimes(1);
    fetchSnapshot.mockReturnValue(pendingFetch.promise);
    rerender(panel());
    expect(container.querySelector('canvas')).toHaveStyle({ display: 'none' });
    expect(screen.getByText('画面连接中…')).toBeInTheDocument();
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
    await advance(3000);
    expect(screen.getByText('画面连接中…')).toBeInTheDocument();
    expect(drawImage).toHaveBeenCalledTimes(1);
  });

  it('closes an old bitmap after remount without publishing it into the new panel', async () => {
    const pendingDecode = deferred<ImageBitmap>();
    const pendingFetch = deferred<Response>();
    const lateFrame = bitmap();
    decodeBitmap.mockReturnValueOnce(pendingDecode.promise);
    const previous = render(panel());
    await flush();
    const oldSignal = fetchSnapshot.mock.calls[0][1]!.signal!;
    previous.unmount();
    fetchSnapshot.mockReturnValue(pendingFetch.promise);
    const { container } = render(panel());
    expect(oldSignal.aborted).toBe(true);
    await act(async () => { pendingDecode.resolve(lateFrame); });
    expect(lateFrame.close).toHaveBeenCalledTimes(1);
    expect(drawImage).not.toHaveBeenCalled();
    expect(onImageLoad).not.toHaveBeenCalled();
    expect(container.querySelector('canvas')).toHaveStyle({ display: 'none' });
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
  });

  it('keeps a pending decode across ordinary callback and overlay rerenders', async () => {
    const pendingDecode = deferred<ImageBitmap>();
    const updatedLoad = vi.fn();
    decodeBitmap.mockReturnValueOnce(pendingDecode.promise);
    const { rerender } = render(panel());
    await flush();
    const signal = fetchSnapshot.mock.calls[0][1]!.signal!;
    rerender(
      <GeometryVideoPanel
        snapshot src="/snapshot/raw" alt="摄像头画面" onImageLoad={updatedLoad}
        overlay={<span>更新的棋盘叠加层</span>}
      />,
    );
    expect(fetchSnapshot).toHaveBeenCalledTimes(1);
    expect(signal.aborted).toBe(false);
    await act(async () => { pendingDecode.resolve(bitmap()); });
    expect(updatedLoad).toHaveBeenCalledExactlyOnceWith({ width: 640, height: 480 });
    expect(onImageLoad).not.toHaveBeenCalled();
    expect(screen.getByText('更新的棋盘叠加层')).toBeInTheDocument();
  });

  it('closes a decoded bitmap even when drawing fails', async () => {
    const failedFrame = bitmap();
    decodeBitmap.mockResolvedValueOnce(failedFrame);
    drawImage.mockImplementationOnce(() => { throw new Error('draw failed'); });
    const { container } = render(panel());
    await flush();
    expect(failedFrame.close).toHaveBeenCalledTimes(1);
    expect(container.querySelector('canvas')).toHaveStyle({ display: 'none' });
    expect(screen.queryByText('棋盘几何叠加层')).toBeNull();
  });
});
