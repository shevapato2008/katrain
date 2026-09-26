import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminApiError, createAdminApi } from '../../api/client';
import TrainingDashboard from './TrainingDashboard';
import type { TrainingModel, TrainingRun, TrainingStatus } from './types';

const runId = '03170c3c-44fb-484b-a80c-1ca47a4099fa';
const datasetId = `dataset-${'a'.repeat(64)}`;
const params = { epochs: 100, batch: 8, imgsz: 960, seed: 0, device: '0', amp: false, plots: false, workers: 0 };
const run = (id = runId): TrainingRun => ({ id, state: 'running', created_at: 'now', started_at: 'now', ended_at: null, observed_at: 'now', dataset_id: datasetId, dataset_manifest_sha256: 'b'.repeat(64), weights_id: 'trusted', augmentation: 'stones-standard', mode: 'stones2', class_names: ['black', 'white'], parameters: params, epoch: 12, total_epochs: 100, metrics: { map50: null, precision: null, recall: null }, log_tail: 'epoch 12 from this run', error: null, model_id: null });
function mockApi(active = false) {
  const api = createAdminApi();
  let status: TrainingStatus = { enabled: true, state: active ? 'running' : 'idle', reason: null, observed_at: 'now', active_run_id: active ? runId : null, gpu_ids: ['0'] };
  let current = active ? run() : null;
  api.trainingStatus = vi.fn(async () => ({ ...status }));
  api.trainingDatasets = vi.fn(async () => [{ id: datasetId, manifest_sha256: 'b'.repeat(64), mode: 'stones2', class_names: ['black', 'white'], train_count: 2, val_count: 1 }]);
  api.trainingPresets = vi.fn(async () => ({ weights: [{ id: 'trusted', sha256: 'c'.repeat(64) }], augmentations: [{ id: 'stones-standard', mode: 'stones2' }], limits: { epochs: [1, 300], batch: [4, 8], imgsz: [640, 960], seed: [0, 2147483647] } }));
  api.trainingRuns = vi.fn(async () => current ? [structuredClone(current)] : []);
  api.trainingRun = vi.fn(async () => structuredClone(current!));
  api.trainingModels = vi.fn(async () => []);
  api.trainingStart = vi.fn(async () => { current = run(); status = { ...status, active_run_id: runId, state: 'running' }; return structuredClone(current); });
  api.trainingCancel = vi.fn(async () => { current = { ...current!, state: 'cancelling' }; status.state = 'cancelling'; return structuredClone(current); });
  return { api, setStatus: (next: TrainingStatus) => { status = next; } };
}
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
});
afterEach(() => { vi.restoreAllMocks(); vi.useRealTimers(); });

describe('real training dashboard', () => {
  it('reads only capability status while disabled, without invented GPU, run or metrics', async () => {
    const { api, setStatus } = mockApi();
    setStatus({ enabled: false, state: 'unknown', reason: 'Mac local training disabled', observed_at: 'now', active_run_id: null, gpu_ids: [] });
    render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    await screen.findByText('Mac local training disabled');
    expect(api.trainingDatasets).not.toHaveBeenCalled();
    expect(api.trainingStart).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: '创建运行 · 未启用' })).toBeDisabled();
    expect(screen.queryByText(/GPU 0|run-demo|dataset-demo|mAP50/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '刷新训练状态' })).toBeEnabled();
  });

  it('starts only explicitly confirmed allowlist input, with one UUID and no automatic training', async () => {
    const { api } = mockApi(); const user = userEvent.setup();
    render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    const create = await screen.findByRole('button', { name: '创建新运行' });
    await waitFor(() => expect(create).toBeEnabled());
    expect(api.trainingStart).not.toHaveBeenCalled();
    await user.click(create);
    const dialog = screen.getByRole('dialog', { name: '创建单卡运行' });
    expect(dialog).toHaveTextContent(datasetId);
    await user.click(within(dialog).getByRole('button', { name: '返回' }));
    expect(api.trainingStart).not.toHaveBeenCalled();
    await user.click(create);
    await user.click(screen.getByRole('button', { name: '确认操作' }));
    await waitFor(() => expect(api.trainingStart).toHaveBeenCalledOnce());
    expect(vi.mocked(api.trainingStart).mock.calls[0][0]).toMatchObject({ dataset_id: datasetId, dataset_manifest_sha256: 'b'.repeat(64), weights_id: 'trusted', augmentation: 'stones-standard', gpu_id: '0', epochs: 100, batch: 8, imgsz: 960, seed: 0, confirmed: true });
    expect(vi.mocked(api.trainingStart).mock.calls[0][0].request_id).toMatch(/^[a-f0-9-]{36}$/);
    await screen.findByText('Epoch 12 / 100');
  });

  it('keeps same-run observations and never treats cancellation intent as an exited process', async () => {
    const { api } = mockApi(true); const user = userEvent.setup();
    render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    await screen.findByText('Epoch 12 / 100');
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(screen.getByLabelText('运行日志')).toHaveTextContent('epoch 12 from this run');
    expect(screen.getByRole('button', { name: '已有占用 · 不并行启动' })).toBeDisabled();
    await user.click(screen.getByRole('button', { name: '取消此运行' }));
    expect(api.trainingCancel).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: '确认操作' }));
    await waitFor(() => expect(api.trainingCancel).toHaveBeenCalledWith(runId, true, expect.any(AbortSignal)));
    await screen.findByText('正在取消 · 等待本运行进程组退出');
    expect(screen.queryByText('进程已退出')).not.toBeInTheDocument();
  });

  it('preserves request UUID on an uncertain create failure rather than creating a second run', async () => {
    const { api } = mockApi(); const user = userEvent.setup();
    api.trainingStart = vi.fn().mockRejectedValueOnce(new AdminApiError(0, 'response lost')).mockResolvedValueOnce(run());
    render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('button', { name: '创建新运行' })).toBeEnabled());
    await user.click(screen.getByRole('button', { name: '创建新运行' }));
    await user.click(screen.getByRole('button', { name: '确认操作' }));
    await screen.findByText('response lost');
    await user.click(screen.getByRole('button', { name: '重试创建请求' }));
    await user.click(screen.getByRole('button', { name: '确认操作' }));
    await waitFor(() => expect(api.trainingStart).toHaveBeenCalledTimes(2));
    expect(vi.mocked(api.trainingStart).mock.calls[0][0]).toEqual(vi.mocked(api.trainingStart).mock.calls[1][0]);
  });

  it('stops polling and aborts all reads on unauthorized or unmount', async () => {
    const { api } = mockApi(); const unauthorized = vi.fn();
    api.trainingStatus = vi.fn(async () => { throw new AdminApiError(401, 'expired'); });
    render(<TrainingDashboard api={api} onUnauthorized={unauthorized} onCapture={vi.fn()} />);
    await waitFor(() => expect(unauthorized).toHaveBeenCalledOnce());
    expect(vi.mocked(api.trainingStatus).mock.calls[0][0]?.aborted).toBe(true);
    expect(api.trainingDatasets).not.toHaveBeenCalled();
  });

  it('observes the active worker while viewing history, without mixing its metrics into that history', async () => {
    vi.useFakeTimers();
    const { api, setStatus } = mockApi(true);
    const history = { ...run('6496464d-c904-4203-ab26-86c7f01dd4be'), state: 'completed' as const, epoch: 100, metrics: { map50: 0.31, precision: null, recall: null } };
    let finished = false;
    api.trainingRuns = vi.fn(async () => [run(), history]);
    api.trainingRun = vi.fn(async (id) => {
      if (id === history.id) return history;
      if (finished) {
        setStatus({ enabled: true, state: 'idle', reason: null, observed_at: 'later', active_run_id: null, gpu_ids: ['0'] });
        return { ...run(), state: 'completed', epoch: 100, metrics: { map50: 0.99, precision: null, recall: null } };
      }
      return run();
    });
    render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    await act(async () => {});
    await act(async () => { fireEvent.change(screen.getByRole('combobox', { name: '运行历史' }), { target: { value: history.id } }); });
    finished = true;
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(vi.mocked(api.trainingRun).mock.calls.filter(([id]) => id === runId)).toHaveLength(3);
    expect(screen.getByText(history.id)).toBeInTheDocument();
    expect(screen.getByText('0.31')).toBeInTheDocument();
    expect(screen.queryByText('0.99')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '创建新运行' })).toBeEnabled();
    expect(api.trainingDatasets).toHaveBeenCalledOnce();
    expect(api.trainingPresets).toHaveBeenCalledOnce();
  });

  it('reads published models after the initial run observation can publish its completed artifact', async () => {
    const { api, setStatus } = mockApi(true);
    const model: TrainingModel = { id: `model-${'d'.repeat(64)}`, run_id: runId, dataset_id: datasetId, dataset_manifest_sha256: 'b'.repeat(64), mode: 'stones2', class_names: ['black', 'white'], weights_sha256: 'e'.repeat(64), weights_bytes: 123, manifest_sha256: 'f'.repeat(64), parameters: params, created_at: 'later' };
    let published = false;
    api.trainingRun = vi.fn(async () => {
      published = true;
      setStatus({ enabled: true, state: 'idle', reason: null, observed_at: 'later', active_run_id: null, gpu_ids: ['0'] });
      return { ...run(), state: 'completed', model_id: model.id, epoch: 100 };
    });
    api.trainingModels = vi.fn(async () => published ? [model] : []);
    render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    await waitFor(() => expect(screen.getByRole('table', { name: '模型版本' })).toHaveTextContent('model-dddddddddddddddd'));
    expect(api.trainingRun).toHaveBeenCalledOnce();
    expect(screen.getByRole('button', { name: '创建新运行' })).toBeEnabled();
  });

  it('does not rescan successful dataset and preset catalogs when subsequent run observations fail', async () => {
    vi.useFakeTimers();
    const { api } = mockApi(true);
    api.trainingRun = vi.fn(async () => { throw new AdminApiError(503, 'worker observation unavailable'); });
    render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    await act(async () => {});
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(api.trainingRun).toHaveBeenCalledTimes(4);
    expect(api.trainingDatasets).toHaveBeenCalledOnce();
    expect(api.trainingPresets).toHaveBeenCalledOnce();
    expect(screen.getByText('worker observation unavailable')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^创建运行/ })).toBeDisabled();
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: '刷新训练状态' })); });
    expect(api.trainingDatasets).toHaveBeenCalledTimes(2);
  });

  it('serializes two-second polls and cannot replace a selected run with an old response', async () => {
    vi.useFakeTimers();
    const { api } = mockApi(true);
    const history = { ...run('6496464d-c904-4203-ab26-86c7f01dd4be'), state: 'completed' as const, epoch: 100, ended_at: 'then' };
    api.trainingRuns = vi.fn(async () => [run(), history]);
    let complete!: (value: TrainingRun) => void;
    let activeCalls = 0;
    api.trainingRun = vi.fn(async (id) => {
      if (id === history.id) return history;
      if (++activeCalls === 2) return new Promise<TrainingRun>((resolve) => { complete = resolve; });
      return run();
    });
    const view = render(<TrainingDashboard api={api} onUnauthorized={vi.fn()} onCapture={vi.fn()} />);
    await act(async () => {});
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    expect(api.trainingRun).toHaveBeenCalledTimes(2);
    expect(api.trainingDatasets).toHaveBeenCalledOnce();
    expect(api.trainingModels).toHaveBeenCalledOnce();
    await act(async () => { await vi.advanceTimersByTimeAsync(6000); });
    expect(api.trainingRun).toHaveBeenCalledTimes(2);
    const oldSignal = vi.mocked(api.trainingRun).mock.calls[1][1];
    await act(async () => { fireEvent.change(screen.getByRole('combobox', { name: '运行历史' }), { target: { value: history.id } }); });
    await act(async () => { complete({ ...run(), epoch: 99 }); });
    expect(oldSignal?.aborted).toBe(true);
    expect(screen.getByText(history.id)).toBeInTheDocument();
    expect(screen.queryByText('Epoch 99 / 100')).not.toBeInTheDocument();
    view.unmount();
    expect(vi.mocked(api.trainingRun).mock.calls.at(-1)?.[1]?.aborted).toBe(true);
  });
});
