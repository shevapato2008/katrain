import { render, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import TrainingPage, { type TrainingProps } from './TrainingPage';
import type { TrainingRun } from './types';

const parameters = { epochs: 100, batch: 8, imgsz: 960, seed: 0 };
const observed: TrainingRun = { id: 'run-test', state: 'running', created_at: 'now', started_at: 'now', ended_at: null, observed_at: 'now', dataset_id: 'dataset-test', dataset_manifest_sha256: 'test-hash', weights_id: 'registered', augmentation: 'stones-standard', mode: 'stones2', class_names: ['black', 'white'], parameters: { ...parameters, device: '0', amp: false, plots: false, workers: 0 }, epoch: 12, total_epochs: 100, metrics: { map50: null, precision: null, recall: null }, log_tail: 'run-test epoch 12', error: null, model_id: null };
const props = (): TrainingProps => ({
  status: { enabled: false, state: 'unknown', reason: 'Not enabled', observed_at: 'now', active_run_id: null, gpu_ids: [] },
  datasets: [], presets: null, runs: [], run: null, models: [], parameters,
  selection: { dataset_id: '', weights_id: '', augmentation: '', gpu_id: '' }, pendingAction: null,
  busy: '', error: '', message: '', canCreate: false, canCancel: false, retryCreate: false, authorized: true,
  onSelectionChange: vi.fn(), onParametersChange: vi.fn(), onCreate: vi.fn(), onCancel: vi.fn(), onDismiss: vi.fn(), onConfirm: vi.fn(), onRefresh: vi.fn(), onRunChange: vi.fn(), onCapture: vi.fn(),
});
describe('real training presentation', () => {
  it('does not invent a device, run, metric or model when disabled', () => {
    render(<TrainingPage {...props()} />);
    expect(screen.getByRole('combobox', { name: '训练 GPU' })).toHaveTextContent('尚未核实可预留 GPU');
    expect(screen.getByRole('button', { name: '创建运行 · 未启用' })).toBeDisabled();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.queryByText(/GPU 0|run-test|mAP50|示例|示意/)).not.toBeInTheDocument();
    expect(document.querySelector('details')).not.toHaveAttribute('open');
  });
  it('keeps observed current-run parameters separate from the creation draft and null metrics empty', () => {
    const value = props();
    render(<TrainingPage {...value} status={{ ...value.status!, enabled: true, state: 'running', active_run_id: observed.id, gpu_ids: ['0'] }} run={observed} parameters={{ ...parameters, batch: 4 }} canCancel />);
    expect(screen.getByText('Epoch 12 / 100')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(screen.getByText('imgsz 960 · batch 8 · seed 0')).toBeInTheDocument();
    expect(screen.getByText('训练参数 · 100 epoch · 960 px · batch 4 · seed 0')).toBeInTheDocument();
    expect(screen.getByLabelText('运行日志')).toHaveTextContent(observed.id);
    expect(screen.getByRole('button', { name: '已有占用 · 不并行启动' })).toBeDisabled();
  });
  it('never maps an interrupted run to cancelled or releases the global create gate for a completed history selection', () => {
    const value = props();
    const { rerender } = render(<TrainingPage {...value} status={{ ...value.status!, enabled: true, state: 'interrupted', active_run_id: observed.id }} run={{ ...observed, state: 'interrupted', error: 'Previous group exit unknown' }} />);
    expect(screen.getByText('运行中断 · 进程组退出尚未核实')).toBeInTheDocument();
    expect(screen.queryByText('进程已退出')).not.toBeInTheDocument();
    rerender(<TrainingPage {...value} status={{ ...value.status!, enabled: true, state: 'busy', reason: 'Lease held' }} run={{ ...observed, state: 'completed', epoch: 100 }} />);
    expect(screen.getByRole('button', { name: '已有占用 · 不并行启动' })).toBeDisabled();
  });
  it('renders actual published hashes and supplied metrics without a download action', () => {
    const value = props();
    render(<TrainingPage {...value} status={{ ...value.status!, enabled: true, state: 'idle' }} run={{ ...observed, state: 'completed', epoch: 100, metrics: { map50: .92, precision: .93, recall: .9 }, model_id: 'model-real' }} models={[{ id: 'model-real', run_id: observed.id, dataset_id: observed.dataset_id, dataset_manifest_sha256: 'test-hash', mode: 'stones2', class_names: ['black', 'white'], weights_sha256: 'verified-checkpoint-hash', weights_bytes: 200, manifest_sha256: 'actual-manifest-hash', parameters: observed.parameters, created_at: 'now' }]} />);
    expect(within(screen.getByRole('table')).getByText('model-real…')).toBeInTheDocument();
    expect(screen.getByText('0.92')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下载 · 待授权' })).toBeDisabled();
  });
});
