import { useEffect, useRef } from 'react';
import { Activity, CircleCheck, CircleHelp, CircleX, Clock3, RefreshCw } from 'lucide-react';
import type { TrainingDataset, TrainingModel, TrainingParameters, TrainingPresets, TrainingRun, TrainingStartInput, TrainingStatus } from './types';
import './TrainingPage.css';

export type TrainingSelection = { dataset_id: string; weights_id: string; augmentation: string; gpu_id: string };
export type TrainingPending = { kind: 'create'; input: TrainingStartInput } | { kind: 'cancel'; run_id: string };
export type TrainingProps = {
  status: TrainingStatus | null; datasets: TrainingDataset[]; presets: TrainingPresets | null; runs: TrainingRun[]; run: TrainingRun | null; models: TrainingModel[];
  parameters: TrainingParameters; selection: TrainingSelection; pendingAction: TrainingPending | null; busy: string; error: string; message: string;
  canCreate: boolean; canCancel: boolean; retryCreate: boolean; authorized: boolean;
  onSelectionChange: (value: TrainingSelection) => void; onParametersChange: (value: TrainingParameters) => void;
  onCreate: () => void; onCancel: () => void; onDismiss: () => void; onConfirm: () => void; onRefresh: () => void;
  onRunChange: (id: string) => void; onCapture: () => void;
};
const labels = { unknown: '服务未核实', idle: '尚无活动运行', busy: '资源占用未核实', starting: '启动中', running: '运行中', cancelling: '正在取消', interrupted: '中断 · 退出待核实', failed: '失败', completed: '完成', cancelled: '已取消' };
export default function TrainingPage(props: TrainingProps) {
  const { status, datasets, presets, runs, run, models, parameters, selection, pendingAction, busy, error, message } = props;
  const enabled = !!status?.enabled && props.authorized;
  const reserved = !!status?.active_run_id || status?.state === 'busy' || status?.state === 'interrupted' || !!status?.reason;
  const locked = !enabled || !!busy || reserved || (!!error && !props.retryCreate);
  const dataset = datasets.find((item) => item.id === selection.dataset_id);
  const state = run?.state ?? status?.state ?? 'unknown';
  const running = run?.state === 'running';
  const completed = run?.state === 'completed';
  const failed = run?.state === 'failed';
  const Icon = state === 'unknown' ? CircleHelp : failed ? CircleX : completed ? CircleCheck : running ? Activity : Clock3;
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!pendingAction || !dialog) return;
    dialog.showModal();
    return () => { dialog.close(); };
  }, [pendingAction]);
  const change = (key: keyof TrainingParameters, value: string) => props.onParametersChange({ ...parameters, [key]: Number(value) });
  const select = (key: keyof TrainingSelection, value: string) => props.onSelectionChange({ ...selection, [key]: value });
  const metric = (value: number | null) => value === null ? '—' : value.toFixed(2);
  const progressLabel = !run ? '' : completed ? '训练结束' : running ? 'Epoch ' + run.epoch + ' / ' + run.total_epochs : failed ? '在 Epoch ' + run.epoch + ' 失败' : run.state === 'starting' ? '正在启动独立运行' : run.state === 'cancelling' ? '正在取消 · 等待本运行进程组退出' : run.state === 'interrupted' ? '运行中断 · 进程组退出尚未核实' : '已取消运行';
  return <main className="training-page" data-state={state}>
    <div className="training-heading"><div><h1>视觉实验室</h1><p>测试机 · 训练运行与模型版本</p></div><div className="training-location"><Icon aria-hidden="true" />{error ? '上次状态 · 当前未核实' : enabled ? '训练状态 · 当前后台服务' : '训练能力未启用'}<button className="training-button" type="button" aria-label="刷新训练状态" disabled={!!busy || !props.authorized} onClick={props.onRefresh}><RefreshCw aria-hidden="true" /></button></div></div>
    <div className="training-content">
      {(status?.reason || !enabled) && <p className="training-demo">{status?.reason ?? '仅测试机 test 环境、显式启用并核实资源后可训练；Mac local 始终禁用，不会暗中连接远端。'}</p>}
      {error && <div className="training-feedback" role="alert"><span>{error}</span><button type="button" className="training-button" disabled={!!busy || !props.authorized} onClick={props.onRefresh}>重试读取</button></div>}
      {message && <p className="training-feedback" role="status">{message}</p>}
      <nav className="training-steps" aria-label="视觉实验室流程"><button type="button" disabled={!!busy} onClick={props.onCapture}><b>1</b>采集与数据集</button><i className="training-step-line" /><span className="active"><b>2</b>训练与模型</span><i className="training-step-line" /><span><b>3</b>本机部署与诊断</span></nav>
      <div className="training-grid">
        <section className="training-panel"><div className="training-panel-head"><h2>创建训练运行</h2><small>固定参数 · 单卡</small></div>
          <form className="training-form" onSubmit={(event) => { event.preventDefault(); if (props.canCreate) props.onCreate(); }}>
            <label className="training-field">冻结数据集<select disabled={locked} value={selection.dataset_id} onChange={(event) => select('dataset_id', event.target.value)}>{datasets.length ? datasets.map((item) => <option key={item.id} value={item.id}>{item.id.slice(0, 22)}… · {item.mode} · {item.train_count}/{item.val_count}</option>) : <option value="">尚无已核实的测试机数据集</option>}</select></label>
            <div className="training-schema">{dataset ? <><span>{dataset.class_names.map((name, id) => name + ' ' + id).join(' · ')}</span><br /><span title={dataset.manifest_sha256}>清单 SHA256 {dataset.manifest_sha256.slice(0, 16)}…</span></> : '类目与清单哈希：尚未读取'}</div>
            <div className="training-form-row"><label className="training-field">预训练权重<select disabled={locked} value={selection.weights_id} onChange={(event) => select('weights_id', event.target.value)}>{presets?.weights.length ? presets.weights.map((item) => <option key={item.id} value={item.id}>{item.id}</option>) : <option value="">待校验权重</option>}</select></label><label className="training-field">增强方案<select disabled={locked} value={selection.augmentation} onChange={(event) => select('augmentation', event.target.value)}>{presets?.augmentations.filter((item) => item.mode === dataset?.mode).map((item) => <option key={item.id} value={item.id}>{item.id}</option>)}{!dataset && <option value="">待核实类目</option>}</select></label></div>
            <label className="training-field">训练 GPU<select disabled={locked} value={selection.gpu_id} onChange={(event) => select('gpu_id', event.target.value)}>{enabled && status.gpu_ids.length ? status.gpu_ids.map((id) => <option key={id} value={id}>GPU {id} · 已登记预留单卡</option>) : <option value="">尚未核实可预留 GPU</option>}</select></label>
            <details className="training-advanced"><summary>训练参数 · {parameters.epochs} epoch · {parameters.imgsz} px · batch {parameters.batch} · seed {parameters.seed}</summary>
              <div className="training-form-row"><label className="training-field">Epoch<input required type="number" min={presets?.limits.epochs[0] ?? 1} max={presets?.limits.epochs[1] ?? 300} value={parameters.epochs} disabled={locked} onChange={(event) => change('epochs', event.target.value)} /></label><label className="training-field">Batch<select value={parameters.batch} disabled={locked} onChange={(event) => change('batch', event.target.value)}>{(presets?.limits.batch ?? [8, 4]).map((value) => <option key={value} value={value}>{value}</option>)}</select></label></div>
              <div className="training-form-row"><label className="training-field">图像尺寸<select value={parameters.imgsz} disabled={locked} onChange={(event) => change('imgsz', event.target.value)}>{(presets?.limits.imgsz ?? [960, 640]).map((value) => <option key={value} value={value}>{value}</option>)}</select></label><label className="training-field">Seed<input required type="number" min={presets?.limits.seed[0] ?? 0} max={presets?.limits.seed[1] ?? 2147483647} value={parameters.seed} disabled={locked} onChange={(event) => change('seed', event.target.value)} /></label></div>
            </details>
            <p className="training-help">{!enabled ? '训练能力尚未启用。远程访问与真实训练均需单独授权；本页不会抢占 KataGo 或自动下载权重。' : reserved ? '已有运行或未核实占用，不能并行启动。取消须确认本运行进程组退出后才释放单卡。' : props.retryCreate ? '创建请求结果未核实；重试使用同一 UUID 和原参数，不另建运行。' : '仅使用已冻结校验的数据集、登记本地权重与预留单卡；不允许隐式下载。'}</p>
            <button type={props.retryCreate ? 'button' : 'submit'} className="training-button primary full" disabled={!props.canCreate || !!busy} onClick={props.retryCreate ? props.onCreate : undefined}>{!enabled ? '创建运行 · 未启用' : props.retryCreate ? '重试创建请求' : reserved ? '已有占用 · 不并行启动' : '创建新运行'}</button>
          </form>
        </section>
        <div>
          <section className="training-panel"><div className="training-panel-head"><h2>当前运行</h2>{runs.length > 0 && <label className="training-history">运行历史<select disabled={!!busy} value={run?.id ?? ''} onChange={(event) => props.onRunChange(event.target.value)}>{!run && <option value="">选择已保存运行</option>}{runs.map((item) => <option key={item.id} value={item.id}>{item.id.slice(0, 8)} · {labels[item.state]}</option>)}</select></label>}<span className="training-status" data-status={state}><Icon aria-hidden="true" />{labels[state]}</span></div>
            {!run ? <div className="training-empty"><strong>{!status ? '尚未读取训练服务' : !enabled ? '训练能力未启用' : '尚无已读取的训练运行'}</strong><p>没有核实结果时，不展示在线设备、日志或指标。创建与取消均需明确确认。</p></div> : <div className="training-run-body">
              <p className="training-run-id">{run.id}<small className="training-observation">上次观察：{run.observed_at}{error ? ' · 已过期，写入禁用' : ''}</small></p>
              <div className="training-progress-row"><strong>{progressLabel}</strong><span>{completed ? run.epoch + ' / ' + run.total_epochs : running ? Math.round(run.epoch / run.total_epochs * 100) + '% · 等待后续 epoch' : failed ? '未发布新模型' : run.state === 'cancelled' ? '进程已退出' : '仍保留运行占用'}</span></div>
              <progress value={run.epoch} max={run.total_epochs} aria-label="运行 epoch 进度" />
              <dl className="training-metrics"><div><dt>mAP50</dt><dd>{metric(run.metrics.map50)}</dd></div><div><dt>Precision</dt><dd>{metric(run.metrics.precision)}</dd></div><div><dt>Recall</dt><dd>{metric(run.metrics.recall)}</dd></div></dl>
              <p className="training-help">{Object.values(run.metrics).every((value) => value === null) ? '尚无验证指标；不填 0，不从其他 run 复制。' : '指标来自此 run 的验证观察；模型只在产物校验后发布。'}</p>
              <div className="training-meta"><span>GPU {run.parameters.device} · 单卡</span><span>imgsz {run.parameters.imgsz} · batch {run.parameters.batch} · seed {run.parameters.seed}</span><span title={run.dataset_id + ' · ' + run.dataset_manifest_sha256}>数据集：{run.dataset_id.slice(0, 22)}…</span></div>
              {(run.error || failed || run.state === 'interrupted') && <div className="training-error" role="alert"><strong>{run.error ?? '运行状态或进程退出尚待核实'}</strong>{failed ? '本运行已退出；未发布新模型，旧版本保留。调整配置后可显式新建，不会自动重启。' : '退出未核实时不能启动其他运行，也不会按保存的 PID 接管或杀进程。'}</div>}
              <div className="training-log-title"><strong>运行日志</strong><small>同一 run · 有界尾部 16 KiB</small></div>
              <pre className="training-log" aria-label="运行日志">{run.log_tail || '尚无运行日志'}</pre>
              <div className="training-run-actions">{running && <button className="training-button" type="button" disabled={!props.canCancel || !!busy} onClick={props.onCancel}>取消此运行</button>}{failed && <button className="training-button" type="button" disabled={!props.canCreate || !!busy} onClick={props.onCreate}>按当前配置新建</button>}</div>
            </div>}
          </section>
          <section className="training-panel training-models"><div className="training-panel-head"><h2>模型版本</h2><small>校验通过后只读保存</small></div>
            {models.length ? <table className="training-model-table" aria-label="模型版本"><thead><tr><th>版本 / 来源</th><th>类目 / 验证</th><th>Mac 获取</th></tr></thead><tbody>{models.map((model) => <tr key={model.id}><td title={model.id}>{model.id.slice(0, 22)}…<small title={model.run_id}>{model.run_id.slice(0, 12)}…</small></td><td>{model.class_names.join(' · ')}<small title={model.weights_sha256}>best.pt SHA256 {model.weights_sha256.slice(0, 12)}…</small></td><td><button className="training-button" type="button" disabled>下载 · 待授权</button></td></tr>)}</tbody></table> : <div className="training-model-empty">{!enabled ? '尚未读取真实模型版本。' : '尚无已校验发布的模型；不会用 last.pt 冒充完成的 best.pt。'}</div>}
          </section>
        </div>
      </div><p className="training-foot">只允许已冻结且清单校验一致的数据集。首版一次一运行、单 GPU；双卡 DDP 尚未验证。</p>
    </div>
    {pendingAction && <dialog ref={dialogRef} className="training-dialog" aria-label={pendingAction.kind === 'cancel' ? '取消当前运行' : '创建单卡运行'} onCancel={props.onDismiss}>
      <h2>{pendingAction.kind === 'cancel' ? '取消当前运行' : '创建单卡运行'}</h2>
      <p>{pendingAction.kind === 'cancel' ? '仅请求停止 ' + pendingAction.run_id + ' 的自建进程组；确认退出前仍保留占用，不影响其他 GPU 进程。' : '数据集 ' + pendingAction.input.dataset_id + '；权重 ' + pendingAction.input.weights_id + '；GPU ' + pendingAction.input.gpu_id + '；' + pendingAction.input.epochs + ' epoch · ' + pendingAction.input.imgsz + ' px · batch ' + pendingAction.input.batch + ' · seed ' + pendingAction.input.seed + '。确认后将请求真实单卡训练，不允许隐式下载。'}</p>
      <div className="training-dialog-actions"><button type="button" className="training-button" disabled={!!busy} onClick={props.onDismiss}>返回</button><button type="button" className="training-button primary" disabled={!!busy || (pendingAction.kind === 'create' ? !props.canCreate : !props.canCancel)} onClick={props.onConfirm}>确认操作</button></div>
    </dialog>}
  </main>;
}
