import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminApiError, createAdminApi } from '../api/client';
import VisionDashboard from './VisionDashboard';
import type { VisionSession, VisionStatus } from './types';

const status = (): VisionStatus => ({
  enabled: true, local_only: true, observed_at: '2026-09-26T03:00:00Z', mode: null,
  camera: { state: 'disconnected', device_id: null, source: 'runtime', updated_at: null },
  led: { state: 'disabled', source: 'runtime', updated_at: null },
  geometry: { state: 'required', revision: null, confidence: null, source: null, updated_at: null },
  sgf: { state: 'none', game_id: null, total_steps: 0, next_step: null, source: 'runtime', updated_at: null },
  dataset: { state: 'none', id: null, count: 0, source: 'runtime', updated_at: null },
});
const session = (): VisionSession => ({
  state: 'draft', game_id: 'game-1', mode: 'stones2', frames: [], next_step: -1, geometry_revision: 'geometry-1',
  steps: [{ kind: 'move', move_index: 0, property: 'B', row: 0, col: 2, color: 'B', removed: [], board_hash: 'board' },
    { kind: 'pass', move_index: 1, property: 'W', row: null, col: null, color: 'W', removed: [], board_hash: 'board' },
    { kind: 'move', move_index: 2, property: 'W', row: 1, col: 3, color: 'W', removed: [], board_hash: 'board2' }],
});
const savedFrame = (index: number) => ({ frame_id: `saved-${index}`, file: 'frame.jpg', sha256: `sha-${index}`, mode: 'stones2' as const, applied_move_index: index, next_guided_move_index: 2, geometry_revision: 'geometry-1', geometry_source: 'opencv_empty_board', captured_at: 'now', camera_seq: index + 2, led_point: null });
function mockApi() {
  const api = createAdminApi();
  let current = status();
  const saved = session();
  api.visionStatus = vi.fn(async () => structuredClone(current));
  api.visionDevices = vi.fn(async () => ({ candidates: [{ device_id: 0, label: 'Camera 0', probed: false as const }] }));
  api.visionSessions = vi.fn(async () => ({ sessions: [], limit: 50, truncated: false }));
  api.visionSession = vi.fn(async () => structuredClone(saved));
  api.visionPreview = vi.fn(async () => ({ frame_id: 'preview-1', camera_seq: 8, captured_at: 'now', captured_at_source: 'runtime', camera_monotonic_ts: 10, geometry_revision: current.geometry.revision, raw_jpeg_base64: 'raw', warped_jpeg_base64: 'warp', geometry_overlay_jpeg_base64: 'grid' }));
  api.visionConnect = vi.fn(async () => { current = { ...current, mode: 'stones2', camera: { ...current.camera, state: 'connected', device_id: 0 } }; return current; });
  api.visionCalibrate = vi.fn(async () => { current.geometry = { ...current.geometry, state: 'ready', revision: 'geometry-1', source: 'opencv_empty_board' }; return current.geometry; });
  api.visionImportSgf = vi.fn(async () => { current.sgf = { ...current.sgf, state: 'loaded', game_id: saved.game_id, total_steps: 3, next_step: -1 }; return { game_id: saved.game_id, sgf_sha256: 'sgf', mode: saved.mode, total_steps: 3, next_step: -1, steps: saved.steps }; });
  api.visionCapture = vi.fn(async (input) => {
    const frame = { frame_id: `frame-${input.move_index}`, file: 'frame.jpg', sha256: 'sha', mode: saved.mode, applied_move_index: input.move_index, next_guided_move_index: input.move_index === -1 ? 0 : 2, geometry_revision: 'geometry-1', geometry_source: 'opencv_empty_board', captured_at: 'now', camera_seq: 12, led_point: null };
    saved.frames.push(frame); saved.state = 'captured'; saved.next_step = frame.next_guided_move_index;
    current.sgf.next_step = saved.next_step; current.dataset = { ...current.dataset, state: 'draft', count: saved.frames.length };
    return frame;
  });
  return { api, saved, setStatus: (next: VisionStatus) => { current = next; } };
}
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
});
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe('live vision journey', () => {
  it('does not open devices automatically and gates calibration and initial capture by explicit confirmation', async () => {
    const { api } = mockApi(); const user = userEvent.setup();
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await screen.findByRole('button', { name: '连接摄像头' });
    expect(api.visionConnect).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: '连接摄像头' }));
    const calibrate = await screen.findByRole('button', { name: '开始空盘标定' });
    expect(calibrate).toBeDisabled();
    await user.click(screen.getByLabelText('棋盘已清空，可开始标定'));
    await user.click(calibrate);
    await waitFor(() => expect(api.visionCalibrate).toHaveBeenCalledWith(true, expect.any(AbortSignal)));
    const file = new File(['(;SZ[19];B[ca])'], 'game.sgf', { type: 'text/plain' });
    await user.upload(screen.getByLabelText('SGF 文件'), file);
    await user.click(screen.getByRole('button', { name: '导入新会话' }));
    await screen.findByText('下一帧：初始空盘');
    const capture = screen.getByRole('button', { name: '确认并采集' });
    expect(capture).toBeDisabled();
    await user.click(screen.getByLabelText('已摆放并核对当前棋面'));
    await user.click(capture);
    await waitFor(() => expect(api.visionCapture).toHaveBeenCalledWith({ game_id: 'game-1', move_index: -1, operator_confirmed: true, overwrite_existing: false }, expect.any(AbortSignal)));
    await screen.findByText('下一手：第 1 手 · 黑棋 C19');
    expect(screen.getByRole('button', { name: '确认并采集' })).toBeDisabled();
    expect(screen.getByRole('button', { name: /上传测试环境/ })).toBeDisabled();
  });

  it('honestly disables nonlocal vision without listing or opening devices', async () => {
    const { api, setStatus } = mockApi(); setStatus({ ...status(), enabled: false });
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await screen.findByText(/此服务未启用本机视觉控制/);
    expect(api.visionDevices).not.toHaveBeenCalled();
    expect(api.visionConnect).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '连接摄像头' })).toBeDisabled();
  });

  it('stops preview requests and clears imagery on 401', async () => {
    const { api, setStatus } = mockApi(); const unauthorized = vi.fn();
    setStatus({ ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 } });
    api.visionPreview = vi.fn(async () => { throw new AdminApiError(401, 'Expired'); });
    render(<VisionDashboard api={api} onUnauthorized={unauthorized} />);
    await waitFor(() => expect(unauthorized).toHaveBeenCalledOnce());
    expect(screen.queryByRole('img', { name: '原始相机画面' })).not.toBeInTheDocument();
  });

  it('aborts unmount and cannot install an old preview after disconnect', async () => {
    const { api, setStatus } = mockApi();
    setStatus({ ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 } });
    let complete!: (value: Awaited<ReturnType<typeof api.visionPreview>>) => void;
    api.visionPreview = vi.fn(() => new Promise((resolve) => { complete = resolve; }));
    api.visionDisconnect = vi.fn(async () => { const next = status(); setStatus(next); return next; });
    const view = render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await waitFor(() => expect(api.visionPreview).toHaveBeenCalledOnce());
    const signal = vi.mocked(api.visionPreview).mock.calls[0][0];
    fireEvent.click(screen.getByRole('button', { name: '断开连接' }));
    await screen.findByRole('button', { name: '连接摄像头' });
    await act(async () => { complete({ frame_id: 'old', captured_at: 'old', captured_at_source: 'runtime', camera_seq: 1, camera_monotonic_ts: 1, geometry_revision: null, raw_jpeg_base64: 'old', warped_jpeg_base64: null, geometry_overlay_jpeg_base64: null }); });
    expect(signal?.aborted).toBe(true);
    expect(screen.queryByRole('img', { name: '原始相机画面' })).not.toBeInTheDocument();
    view.unmount();
    expect(api.visionDisconnect).toHaveBeenCalledOnce();
  });

  it('refreshes authoritative device state after a failed preview and exposes a manual refresh', async () => {
    const { api, setStatus } = mockApi();
    setStatus({ ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 } });
    api.visionPreview = vi.fn(async () => { setStatus(status()); throw new AdminApiError(503, 'Camera frame unavailable'); });
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await waitFor(() => expect(api.visionStatus).toHaveBeenCalledTimes(2));
    expect(screen.getByRole('button', { name: '连接摄像头' })).toBeEnabled();
    expect(screen.getByRole('button', { name: '刷新本机状态' })).toBeEnabled();
    expect(screen.queryByText('本机摄像头已连接')).not.toBeInTheDocument();
  });

  it('restores server progress but requires the currently displayed saved-grid frame before capture', async () => {
    const { api, saved, setStatus } = mockApi(); const user = userEvent.setup();
    let current: VisionStatus = { ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 }, geometry: { ...status().geometry, state: 'ready', revision: 'geometry-1' } };
    setStatus(current); saved.frames = [savedFrame(-1), savedFrame(0)]; saved.next_step = 2; saved.state = 'captured';
    api.visionSessions = vi.fn(async () => ({ sessions: [{ game_id: saved.game_id, state: 'captured', mode: 'stones2', count: 2 }], limit: 50, truncated: false }));
    api.visionResumeSession = vi.fn(async () => {
      current = { ...current, geometry: { ...current.geometry, state: 'stale' }, sgf: { ...current.sgf, game_id: saved.game_id, state: 'loaded', total_steps: 3, next_step: 2 }, dataset: { ...current.dataset, state: 'draft', count: 2 } };
      setStatus(current); return current;
    });
    api.visionVerifyGeometry = vi.fn(async () => { current.geometry = { ...current.geometry, state: 'ready' }; setStatus(current); return current.geometry; });
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: '恢复会话' }));
    await user.selectOptions(screen.getByLabelText('保存的会话'), 'game-1');
    await user.click(screen.getByRole('button', { name: '恢复所选会话' }));
    await screen.findByText('下一手：第 3 手 · 白棋 D18');
    expect(screen.getByRole('button', { name: '确认并采集' })).toBeDisabled();
    const confirm = screen.getByRole('button', { name: '确认保存的标定' });
    expect(confirm).toBeDisabled();
    await waitFor(() => expect(screen.getByLabelText('已检查当前网格，视角与原标定一致')).toBeEnabled());
    await user.click(screen.getByLabelText('显示标定网格'));
    expect(screen.getByLabelText('已检查当前网格，视角与原标定一致')).toBeDisabled();
    await user.click(screen.getByLabelText('显示标定网格'));
    await user.click(screen.getByLabelText('已检查当前网格，视角与原标定一致'));
    await user.click(confirm);
    await waitFor(() => expect(api.visionVerifyGeometry).toHaveBeenCalledWith('game-1', 'preview-1', true, expect.any(AbortSignal)));
    expect(screen.getByRole('button', { name: '确认并采集' })).toBeDisabled();
  });

  it('reviews real labels, requires both retake confirmations, and freezes only an actual returned version', async () => {
    const { api, saved, setStatus } = mockApi(); const user = userEvent.setup();
    saved.state = 'captured'; saved.frames = [savedFrame(-1), savedFrame(0), savedFrame(2)]; saved.next_step = null;
    const current: VisionStatus = { ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 }, geometry: { ...status().geometry, state: 'ready', revision: 'geometry-1' }, sgf: { ...status().sgf, state: 'loaded', game_id: saved.game_id, total_steps: 3, next_step: null }, dataset: { ...status().dataset, state: 'draft', count: 3 } };
    setStatus(current);
    api.visionReviewSample = vi.fn(async () => ({ frame_id: 'saved-0', source_sha256: 'sha-0', geometry_revision: 'geometry-1', geometry_source: 'opencv_empty_board', mode: 'stones2', class_names: ['black', 'white'], boxes: [{ class_id: 0, cx: .3, cy: .4, w: .05, h: .05 }], led_evidence: null, overlay_jpeg_base64: 'overlay', captured_at: 'now', camera_seq: 2, applied_move_index: 0 }));
    api.visionCapture = vi.fn(async () => { saved.frames[1] = { ...savedFrame(0), frame_id: 'retaken-0' }; return saved.frames[1]; });
    api.visionFreezeSession = vi.fn(async () => {
      current.dataset = { ...current.dataset, state: 'frozen', id: 'dataset-real' }; setStatus(current);
      return { id: 'dataset-real', manifest_sha256: 'frozen-sha', idempotent: false, mode: 'stones2', class_names: ['black', 'white'], samples: [{ frame_id: 'saved--1', split: 'train' }, { frame_id: 'retaken-0', split: 'val' }], parameters: { val_fraction: .2 } };
    });
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: /第 1 手 · 黑棋 C19.*查看标签/ }));
    await screen.findByRole('dialog', { name: /样本检查/ });
    expect(screen.getByRole('img', { name: '真实样本标注叠框' })).toHaveAttribute('src', 'data:image/jpeg;base64,overlay');
    expect(screen.getByText('black 1 · white 0')).toBeInTheDocument();
    const retake = screen.getByRole('button', { name: '确认重拍' });
    expect(retake).toBeDisabled();
    await user.click(screen.getByLabelText('需要重拍此帧（保留后续样本）'));
    expect(retake).toBeDisabled();
    await user.click(screen.getByLabelText('已重新摆放并核对这帧对应棋面'));
    await user.click(retake);
    await waitFor(() => expect(api.visionCapture).toHaveBeenCalledWith({ game_id: 'game-1', move_index: 0, operator_confirmed: true, overwrite_existing: true }, expect.any(AbortSignal)));
    await screen.findByText('样本已重拍；后续样本保留。');
    expect(screen.getByRole('button', { name: /第 3 手 · 白棋 D18.*查看标签/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '冻结版本' }));
    await screen.findByText(/只读版本 dataset-real 已冻结；尚未上传/);
    expect(api.visionFreezeSession).toHaveBeenCalledWith('game-1', {}, expect.any(AbortSignal));
    expect(screen.getByRole('button', { name: /上传测试环境/ })).toBeDisabled();
    saved.game_id = 'game-new'; saved.frames = []; saved.state = 'draft'; saved.next_step = -1;
    current.sgf = { ...current.sgf, game_id: 'game-new', next_step: -1 };
    current.dataset = { ...current.dataset, state: 'none', id: null, count: 0 }; setStatus(current);
    await user.click(screen.getByRole('button', { name: '刷新本机状态' }));
    await screen.findByText('下一帧：初始空盘');
    expect(screen.queryByText(/版本 dataset-real/)).not.toBeInTheDocument();
  });

  it('never overlaps preview polls and waits at least 500 ms after completion', async () => {
    const { api, setStatus } = mockApi();
    setStatus({ ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 } });
    let complete!: (value: Awaited<ReturnType<typeof api.visionPreview>>) => void;
    api.visionPreview = vi.fn(() => new Promise((resolve) => { complete = resolve; }));
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await waitFor(() => expect(api.visionPreview).toHaveBeenCalledOnce());
    vi.useFakeTimers();
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(api.visionPreview).toHaveBeenCalledOnce();
    await act(async () => { complete({ frame_id: 'same-frame', captured_at: 'now', captured_at_source: 'runtime', camera_seq: 9, camera_monotonic_ts: 10, geometry_revision: null, raw_jpeg_base64: 'raw', warped_jpeg_base64: 'warp', geometry_overlay_jpeg_base64: null }); });
    expect(screen.getByRole('img', { name: '原始相机画面' })).toHaveAttribute('src', 'data:image/jpeg;base64,raw');
    expect(screen.getByRole('img', { name: '标定后的画面' })).toHaveAttribute('src', 'data:image/jpeg;base64,warp');
    await act(async () => { await vi.advanceTimersByTimeAsync(499); });
    expect(api.visionPreview).toHaveBeenCalledOnce();
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(api.visionPreview).toHaveBeenCalledTimes(2);
  });

  it('does not offer capture when a resumed draft differs from the connected camera mode', async () => {
    const { api, setStatus } = mockApi();
    setStatus({ ...status(), mode: 'led4', camera: { ...status().camera, state: 'connected', device_id: 0 }, geometry: { ...status().geometry, state: 'ready', revision: 'geometry-1' }, sgf: { ...status().sgf, state: 'loaded', game_id: 'game-1', total_steps: 3, next_step: -1 } });
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await screen.findByText(/当前设备或模式与原会话不同/);
    expect(screen.getByLabelText('已摆放并核对当前棋面')).toBeDisabled();
    expect(screen.getByRole('button', { name: '确认并采集' })).toBeDisabled();
  });

  it('keeps the two-Hz preview budget across manual refreshes, not just within a polling loop', async () => {
    vi.useFakeTimers();
    const { api, setStatus } = mockApi();
    setStatus({ ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 } });
    await act(async () => { render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />); });
    expect(api.visionPreview).toHaveBeenCalledOnce();
    await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '刷新本机状态' })); });
    expect(api.visionPreview).toHaveBeenCalledOnce();
    await act(async () => { await vi.advanceTimersByTimeAsync(299); });
    expect(api.visionPreview).toHaveBeenCalledOnce();
    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(api.visionPreview).toHaveBeenCalledTimes(2);
  });

  it('cancels a file read if the still-mounted controller changes operation context', async () => {
    const { api, setStatus } = mockApi(); const user = userEvent.setup();
    setStatus({ ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 }, geometry: { ...status().geometry, state: 'ready', revision: 'geometry-1' } });
    const readers: FileReader[] = [];
    vi.spyOn(FileReader.prototype, 'readAsText').mockImplementation(function (this: FileReader) { readers.push(this); });
    const abort = vi.spyOn(FileReader.prototype, 'abort').mockImplementation(function (this: FileReader) { this.onabort?.(new ProgressEvent('abort') as ProgressEvent<FileReader>); });
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await screen.findByRole('button', { name: '断开连接' });
    await user.upload(screen.getByLabelText('SGF 文件'), new File(['(;SZ[19];B[aa])'], 'game.sgf'));
    await user.click(screen.getByRole('button', { name: '导入新会话' }));
    await user.click(screen.getByRole('button', { name: '刷新本机状态' }));
    await act(async () => { const reader = readers[0]; Object.defineProperty(reader, 'result', { value: '(;SZ[19];B[aa])' }); reader.onload?.(new ProgressEvent('load') as ProgressEvent<FileReader>); });
    expect(abort).toHaveBeenCalled();
    expect(api.visionImportSgf).not.toHaveBeenCalled();
  });

  it('offers a guarded retake when real label inspection rejects a missing LED', async () => {
    const { api, saved, setStatus } = mockApi(); const user = userEvent.setup();
    saved.state = 'captured'; saved.frames = [savedFrame(-1), savedFrame(0)]; saved.next_step = 2;
    setStatus({ ...status(), mode: 'stones2', camera: { ...status().camera, state: 'connected', device_id: 0 }, geometry: { ...status().geometry, state: 'ready', revision: 'geometry-1' }, sgf: { ...status().sgf, state: 'loaded', game_id: 'game-1', total_steps: 3, next_step: 2 }, dataset: { ...status().dataset, state: 'draft', count: 2 } });
    api.visionReviewSample = vi.fn(async () => { throw new AdminApiError(422, 'Expected guide LED is not visible'); });
    render(<VisionDashboard api={api} onUnauthorized={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: /第 1 手 · 黑棋 C19.*查看标签/ }));
    await screen.findByRole('dialog', { name: /样本检查/ });
    expect(screen.getByRole('alert')).toHaveTextContent('Expected guide LED is not visible');
    expect(screen.queryByRole('img', { name: '真实样本标注叠框' })).not.toBeInTheDocument();
    await user.click(screen.getByLabelText('需要重拍此帧（保留后续样本）'));
    expect(screen.getByRole('button', { name: '确认重拍' })).toBeDisabled();
    await user.click(screen.getByLabelText('已重新摆放并核对这帧对应棋面'));
    await user.click(screen.getByRole('button', { name: '确认重拍' }));
    await waitFor(() => expect(api.visionCapture).toHaveBeenCalledWith({ game_id: 'game-1', move_index: 0, operator_confirmed: true, overwrite_existing: true }, expect.any(AbortSignal)));
  });
});
