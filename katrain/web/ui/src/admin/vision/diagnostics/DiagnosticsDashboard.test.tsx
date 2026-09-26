import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AdminApiError, createAdminApi } from '../../api/client';
import DiagnosticsDashboard from './DiagnosticsDashboard';
import type { DiagnosticsSnapshot, DiagnosticsStatus, VisionModels, VisionStatus } from '../types';

const ID_A = 'model-' + 'a'.repeat(64);
const ID_B = 'model-' + 'b'.repeat(64);
const capture = (ready: boolean): VisionStatus => ({
  enabled: true, local_only: true, observed_at: 'now', mode: 'led4', fiducial_mode: 'off',
  camera: { state: ready ? 'connected' : 'disconnected', device_id: ready ? 0 : null, source: 'runtime', updated_at: null },
  led: { state: 'connected', source: 'runtime', updated_at: null },
  geometry: { state: ready ? 'ready' : 'required', revision: ready ? 'geometry-1' : null, confidence: 0.9, source: null, updated_at: null },
  sgf: { state: 'none', game_id: null, total_steps: 0, next_step: null, source: 'runtime', updated_at: null },
  dataset: { state: 'none', id: null, count: 0, source: 'runtime', updated_at: null },
});
const model = (id: string) => ({ id, valid: true, error: null, mode: 'led4' as const, class_names: ['black', 'white', 'led_red', 'led_green'], manifest_sha256: 'f'.repeat(64), parameters: { imgsz: 960 } });
const board = (cells: Record<number, string>) => Array.from({ length: 361 }, (_, index) => cells[index] ?? '0').join('');
const snapshot = (stale = false): DiagnosticsSnapshot => ({
  batch_id: 'batch-12', observed_at: '2026-09-27T01:00:00Z', camera_seq: 340, contributors: [333, 340], contributor_count: 8,
  model_id: ID_A, model_sha256: 'e'.repeat(64), imgsz: 960, class_names: ['black', 'white', 'led_red', 'led_green'], geometry_revision: 'geometry-1',
  reference_participates: false, reference_mode: 'shadow',
  images: { raw: { jpeg_base64: 'raw', width: 960, height: 540 }, warped: { jpeg_base64: 'warp', width: 960, height: 960 }, input: { jpeg_base64: 'input', width: 960, height: 960 } },
  stages: [
    { id: 'raw', image: 'raw', boxes: null, board: null, unavailable: null, derived: false },
    { id: 'warped', image: 'warped', boxes: null, board: null, unavailable: null, derived: false },
    { id: 'nms', image: 'input', boxes: [{ x1: 0.1, y1: 0.1, x2: 0.15, y2: 0.15, class_id: 0, confidence: 0.9 }, { x1: 0.3, y1: 0.3, x2: 0.35, y2: 0.35, class_id: 1, confidence: 0.8 }], board: null, unavailable: null, derived: false },
    { id: 'filtered', image: 'input', boxes: [{ x1: 0.1, y1: 0.1, x2: 0.15, y2: 0.15, class_id: 0, confidence: 0.9, tier: 'keep' }], board: null, unavailable: null, derived: false },
    { id: 'projection', image: null, boxes: null, board: board({ 60: '1', 61: '2' }), unavailable: null, derived: true },
    { id: 'assigned', image: null, boxes: null, board: board({ 60: '1', 62: '2' }), unavailable: null, derived: false },
    { id: 'published', image: null, boxes: null, board: board({ 60: '1' }), unavailable: null, derived: false },
  ],
  stale, age_s: stale ? 6 : 0.2,
});

function mockApi(ready = true) {
  const api = createAdminApi();
  let registry: VisionModels = { models: [model(ID_A), model(ID_B)], current: ID_A, previous: ID_B, loaded_id: ID_A, load_error: null };
  let state: DiagnosticsStatus = { state: 'idle', error: null, started_at: null, model_id: null, snapshot_age_s: null };
  let snap: DiagnosticsSnapshot | null = null;
  api.visionStatus = vi.fn(async () => capture(ready));
  api.visionModels = vi.fn(async () => registry);
  api.diagnosticsStatus = vi.fn(async () => state);
  api.diagnosticsSnapshot = vi.fn(async () => { if (!snap) throw new AdminApiError(404, 'No diagnostic batch yet'); return snap; });
  api.diagnosticsStart = vi.fn(async () => { state = { ...state, state: 'running', model_id: ID_A }; return state; });
  api.diagnosticsStop = vi.fn(async () => { state = { ...state, state: 'idle' }; return state; });
  api.visionActivateModel = vi.fn(async (id: string) => { registry = { ...registry, previous: registry.current, current: id, loaded_id: id }; return registry; });
  api.visionRollbackModel = vi.fn(async () => registry);
  return { api, setSnapshot: (next: DiagnosticsSnapshot | null) => { snap = next; } };
}
beforeEach(() => {
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: function (this: HTMLDialogElement) { this.removeAttribute('open'); } });
});
afterEach(() => { vi.restoreAllMocks(); });

describe('diagnostics dashboard', () => {
  it('never starts without a ready device and sends the operator to the capture page', async () => {
    const { api } = mockApi(false); const toCapture = vi.fn(); const user = userEvent.setup();
    render(<DiagnosticsDashboard api={api} onUnauthorized={vi.fn()} onCapturePage={toCapture} />);
    expect(await screen.findByRole('button', { name: /开始诊断 · 设备未就绪/ })).toBeDisabled();
    expect(screen.getByText('尚无已核实快照')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '去连接与标定' }));
    expect(toCapture).toHaveBeenCalled();
    expect(api.diagnosticsSnapshot).not.toHaveBeenCalled();
  });

  it('activates a registered model only after the confirm dialog', async () => {
    const { api } = mockApi(); const user = userEvent.setup();
    render(<DiagnosticsDashboard api={api} onUnauthorized={vi.fn()} onCapturePage={vi.fn()} />);
    await user.selectOptions(await screen.findByLabelText('登记模型'), ID_B);
    await user.click(screen.getByRole('button', { name: '激活' }));
    const confirm = within(screen.getByRole('dialog')).getByRole('button', { name: '确认激活' });
    expect(confirm).toBeDisabled();
    await user.click(screen.getByLabelText('我理解加载失败不会替换当前版本。'));
    await user.click(confirm);
    await waitFor(() => expect(api.visionActivateModel).toHaveBeenCalledWith(ID_B, expect.any(AbortSignal)));
  });

  it('starts the viewer, shows one real batch per stage, locks model changes, and flags a stale batch', async () => {
    const { api, setSnapshot } = mockApi(); const user = userEvent.setup();
    const view = render(<DiagnosticsDashboard api={api} onUnauthorized={vi.fn()} onCapturePage={vi.fn()} />);
    await user.click(await screen.findByRole('button', { name: '开始诊断' }));
    await user.click(screen.getByLabelText('我已理解 viewer 不参与对局、参考检查与落子确认。'));
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '确认开始' }));
    await waitFor(() => expect(api.diagnosticsStart).toHaveBeenCalled());
    expect(await screen.findByText('正在等待第一个处理批次')).toBeInTheDocument();
    setSnapshot(snapshot());
    expect(await screen.findByText('同一处理批次 · batch-12', {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByRole('img', { name: '原图 / 标定叠图' })).toHaveAttribute('src', 'data:image/jpeg;base64,raw');
    expect(screen.getByRole('button', { name: '激活' })).toBeDisabled();
    expect(screen.getByText('诊断未停止 · 换模前请先停止')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: /NMS 后框/ }));
    expect(screen.getByRole('img', { name: '模型 NMS 后框' })).toHaveAttribute('src', 'data:image/jpeg;base64,input');
    expect(screen.getByText(/2 个 · black 1 · white 1/)).toBeInTheDocument();
    await user.keyboard('5');
    expect(screen.getByRole('img', { name: '原始定位投影 · 诊断派生' })).toBeInTheDocument();
    expect(screen.getByText(/2 格不同（红框）：E16、F16/)).toBeInTheDocument();
    await user.keyboard('{ArrowRight}{ArrowRight}');
    expect(screen.getByText(/1 格未稳定或被否认（橙框）：F16/)).toBeInTheDocument();
    expect(screen.getByText('viewer 未参与')).toBeInTheDocument();
    setSnapshot(snapshot(true));
    expect(await screen.findByText(/整份旧快照 · 6 秒未更新/, {}, { timeout: 3000 })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: '停止诊断' }));
    await waitFor(() => expect(api.diagnosticsStop).toHaveBeenCalled());
    view.unmount();
  });
});
