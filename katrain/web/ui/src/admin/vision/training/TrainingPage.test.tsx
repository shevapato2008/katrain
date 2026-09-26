import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TrainingPage, { type TrainingProps, type TrainingView } from './TrainingPage';
import TrainingFixture from './TrainingFixture';

const parameters = { epochs: 100, batch: 8, imgsz: 960, seed: 0 };
const unknown: TrainingView = { state: 'unknown', designOnly: true, dataset: null, weights: null, augmentation: null, gpu: null, run: null, models: [] };
const running: TrainingView = {
  state: 'running', designOnly: true,
  dataset: { id: 'dataset-test', label: '冻结样例', classNames: ['black', 'white'], manifestSha256: 'demo-sha' },
  weights: 'YOLO11m · 示例', augmentation: '棋子标准 · 示例', gpu: 'GPU 0 · 预留单卡示例',
  run: { id: 'run-test', epoch: 12, totalEpochs: 100, parameters, datasetId: 'dataset-test', gpu: 'GPU 0 · 单卡示例', metrics: { map50: null, precision: null, recall: null }, log: '[design-only] run-test epoch12', error: null }, models: [],
};
const props = (view: TrainingView): TrainingProps => ({ view, parameters, pendingAction: null, onParametersChange: vi.fn(), onCreate: vi.fn(), onCancel: vi.fn(), onDismiss: vi.fn(), onConfirm: vi.fn() });

describe('training fixture presentation', () => {
  it('has no invented metrics, run, GPU, dataset or model before observations', () => {
    render(<TrainingPage {...props(unknown)} />);
    expect(screen.getByText('尚未读取训练服务')).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: '训练 GPU' })).toHaveTextContent('尚未核实可预留 GPU');
    expect(screen.getByRole('combobox', { name: '冻结数据集' })).toHaveTextContent('尚无已核实的测试机数据集');
    expect(screen.getByRole('button', { name: '创建运行 · 待授权' })).toBeDisabled();
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument();
    expect(screen.queryByText('mAP50')).not.toBeInTheDocument();
    expect(screen.queryByText(/run-test|GPU 0|dataset-test/)).not.toBeInTheDocument();
    expect(screen.getByText('尚未读取真实模型版本。')).toBeInTheDocument();
    expect(document.querySelector('details')).not.toHaveAttribute('open');
  });

  it('shows same-run progress, null metrics, bounded logs and locked configuration in running state', () => {
    render(<TrainingPage {...props(running)} />);
    expect(screen.getByText('run-test · 设计示例')).toBeInTheDocument();
    expect(screen.getByText('Epoch 12 / 100')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '12');
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(screen.queryByText('0.00')).not.toBeInTheDocument();
    expect(screen.getByLabelText('运行日志')).toHaveTextContent('run-test epoch12');
    expect(screen.getByRole('combobox', { name: '冻结数据集' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '已有运行 · 不并行启动' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '取消此运行（示意）' })).toBeEnabled();
  });

  it('exposes the supplied failure and explicit new-run recovery, not a silent retry or published model', () => {
    const view: TrainingView = { ...running, state: 'failed', run: { ...running.run!, error: 'CUDA out of memory' } };
    render(<TrainingPage {...props(view)} />);
    expect(screen.getByRole('alert')).toHaveTextContent('CUDA out of memory');
    expect(screen.getByRole('alert')).toHaveTextContent('旧版本保留');
    expect(screen.getByRole('button', { name: '按当前配置新建（示意）' })).toBeEnabled();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows verified-version information only supplied by the completed example and keeps download disabled', () => {
    const view: TrainingView = { ...running, state: 'completed', run: { ...running.run!, epoch: 100, metrics: { map50: .92, precision: .93, recall: .90 } }, models: [{ id: 'model-test', runId: 'run-test', classNames: ['black', 'white'], weightsSha256: 'demo-sha' }] };
    render(<TrainingPage {...props(view)} />);
    const table = screen.getByRole('table', { name: '模型版本' });
    expect(within(table).getByText('model-test')).toBeInTheDocument();
    expect(within(table).getByText('run-test · 示例')).toBeInTheDocument();
    expect(screen.getByText('0.92')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下载 · 待授权' })).toBeDisabled();
    expect(screen.getByText(/设计指标示例，非实测/)).toBeInTheDocument();
  });

  it('keeps demonstration wording out of the pure page when designOnly is false', () => {
    const observed: TrainingView = { ...running, designOnly: false, weights: 'trusted.pt', augmentation: 'stones', gpu: 'GPU 0', dataset: { ...running.dataset!, label: '冻结数据集' }, run: { ...running.run!, gpu: 'GPU 0', log: 'epoch 12' } };
    const { container, rerender } = render(<TrainingPage {...props({ ...observed, state: 'completed', models: [{ id: 'model-real', runId: 'run-real', classNames: ['black', 'white'], weightsSha256: 'verified-sha' }] })} />);
    expect(container).not.toHaveTextContent(/示例|示意|演示/);
    rerender(<TrainingPage {...props(observed)} />);
    expect(container).not.toHaveTextContent(/示例|示意|演示/);
    rerender(<TrainingPage {...props({ ...observed, state: 'failed' })} />);
    expect(container).not.toHaveTextContent(/示例|示意|演示/);
  });
});

describe('isolated training demonstration', () => {
  beforeEach(() => {
    Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
    Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
  });

  it('requires confirmation before the example cancel and lets the operator return without changing state', async () => {
    const user = userEvent.setup();
    render(<TrainingFixture initialState="running" />);
    await user.click(screen.getByRole('button', { name: '取消此运行（示意）' }));
    const dialog = screen.getByRole('dialog', { name: '取消当前运行（设计演示）' });
    expect(dialog).toHaveTextContent('run-demo-20260926');
    await user.click(within(dialog).getByRole('button', { name: '返回' }));
    expect(screen.getByText('运行中 · 示意')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '取消此运行（示意）' }));
    await user.click(screen.getByRole('button', { name: '确认设计操作' }));
    expect(screen.getByText('已取消 · 示意')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('keeps parameter changes in the controller and creates only a confirmed demonstration state', async () => {
    const user = userEvent.setup();
    render(<TrainingFixture initialState="failed" />);
    await user.click(screen.getByText('训练参数 · 100 epoch · 960 px · batch 8 · seed 0'));
    await user.selectOptions(screen.getByRole('combobox', { name: 'Batch' }), '4');
    expect(screen.getByText('训练参数 · 100 epoch · 960 px · batch 4 · seed 0')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '按当前配置新建（示意）' }));
    expect(screen.getByRole('dialog', { name: '创建单卡运行（设计演示）' })).toHaveTextContent('不连接测试机或消耗 GPU');
    expect(screen.getByText('失败 · 示意')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '确认设计操作' }));
    expect(screen.getByText('运行中 · 示意')).toBeInTheDocument();
    expect(screen.getByText('imgsz 960 · batch 4 · seed 0')).toBeInTheDocument();
    expect(screen.queryByText(/性能监控/)).not.toBeInTheDocument();
  });
});
