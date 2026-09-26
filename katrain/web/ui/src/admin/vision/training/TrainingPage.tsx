import { useEffect, useRef } from 'react';
import { Activity, CircleCheck, CircleHelp, CircleX, Clock3 } from 'lucide-react';
import './TrainingPage.css';

export type TrainingParameters = { epochs: number; batch: number; imgsz: number; seed: number };
export type TrainingState = 'unknown' | 'running' | 'failed' | 'completed' | 'cancelled';
export type TrainingView = {
  state: TrainingState; designOnly: boolean;
  dataset: { id: string; label: string; classNames: string[]; manifestSha256: string } | null;
  weights: string | null; augmentation: string | null; gpu: string | null;
  run: { id: string; epoch: number; totalEpochs: number; parameters: TrainingParameters; datasetId: string; gpu: string; metrics: { map50: number | null; precision: number | null; recall: number | null }; log: string; error: string | null } | null;
  models: { id: string; runId: string; classNames: string[]; weightsSha256: string }[];
};
export type TrainingProps = {
  view: TrainingView; parameters: TrainingParameters; pendingAction: 'create' | 'cancel' | null;
  onParametersChange: (value: TrainingParameters) => void; onCreate: () => void; onCancel: () => void;
  onDismiss: () => void; onConfirm: () => void;
};
export default function TrainingPage({ view, parameters, pendingAction, onParametersChange, onCreate, onCancel, onDismiss, onConfirm }: TrainingProps) {
  const unknown = view.state === 'unknown';
  const running = view.state === 'running';
  const completed = view.state === 'completed';
  const failed = view.state === 'failed';
  const locked = unknown || running;
  const run = unknown ? null : view.run;
  const dataset = unknown ? null : view.dataset;
  const models = unknown ? [] : view.models;
  const StatusIcon = unknown ? CircleHelp : failed ? CircleX : completed ? CircleCheck : running ? Activity : Clock3;
  const statusLabel = unknown ? '尚无真实运行' : ({ running: '运行中', failed: '失败', completed: '完成', cancelled: '已取消' })[view.state as Exclude<TrainingState, 'unknown'>];
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    if (!pendingAction || !dialog) return;
    dialog.showModal();
    return () => { dialog.close(); };
  }, [pendingAction]);
  const metric = (value: number | null) => value === null ? '—' : value.toFixed(2);
  const change = (key: keyof TrainingParameters, value: string) => onParametersChange({ ...parameters, [key]: Number(value) });

  return <main className="training-page" data-state={view.state}>
    <div className="training-heading"><div><h1>视觉实验室</h1><p>测试机 · 训练运行与模型版本</p></div><span className="training-location"><StatusIcon aria-hidden="true" />{unknown ? '训练服务未核实' : view.designOnly ? '设计示例 · 非真实服务' : '训练运行状态'}</span></div>
    <div className="training-content">
      {view.designOnly && <p className="training-demo">Fixture 设计示意 · 不连接服务器、不启动训练、不下载模型；示例指标不是实测结果。</p>}
      <nav className="training-steps" aria-label="视觉实验室流程"><span><b>1</b>采集与数据集</span><i className="training-step-line" /><span className="active"><b>2</b>训练与模型</span><i className="training-step-line" /><span><b>3</b>本机部署与诊断</span></nav>
      <div className="training-grid">
        <section className="training-panel"><div className="training-panel-head"><h2>创建训练运行</h2><small>固定参数 · 单卡</small></div>
          <form className="training-form" onSubmit={(event) => { event.preventDefault(); if (!locked) onCreate(); }}>
            <label className="training-field">冻结数据集<select disabled={locked} value={dataset?.id ?? ''} onChange={() => undefined}><option value={dataset?.id ?? ''}>{dataset ? `${dataset.id} · ${dataset.label}` : '尚无已核实的测试机数据集'}</option></select></label>
            <div className="training-schema">{dataset ? `${dataset.classNames.map((name, id) => `${name} ${id}`).join(' · ')} · 清单 SHA256 ${dataset.manifestSha256}${view.designOnly ? '（示意）' : ''}` : '类目与清单哈希：尚未读取'}</div>
            <div className="training-form-row"><label className="training-field">预训练权重<select disabled={locked} value="selected" onChange={() => undefined}><option value="selected">{unknown ? '待校验权重' : view.weights ?? '待校验权重'}</option></select></label><label className="training-field">增强方案<select disabled={locked} value="selected" onChange={() => undefined}><option value="selected">{unknown ? '待核实类目' : view.augmentation ?? '待核实类目'}</option></select></label></div>
            <label className="training-field">训练 GPU<select disabled={locked} value="selected" onChange={() => undefined}><option value="selected">{unknown ? '尚未核实可预留 GPU' : view.gpu ?? '尚未核实可预留 GPU'}</option></select></label>
            <details className="training-advanced"><summary>训练参数 · {parameters.epochs} epoch · {parameters.imgsz} px · batch {parameters.batch} · seed {parameters.seed}</summary>
              <div className="training-form-row"><label className="training-field">Epoch<input type="number" min={1} max={300} value={parameters.epochs} disabled={locked} onChange={(event) => change('epochs', event.target.value)} /></label><label className="training-field">Batch<select value={parameters.batch} disabled={locked} onChange={(event) => change('batch', event.target.value)}><option value={8}>8</option><option value={4}>4</option></select></label></div>
              <div className="training-form-row"><label className="training-field">图像尺寸<select value={parameters.imgsz} disabled={locked} onChange={(event) => change('imgsz', event.target.value)}><option value={960}>960</option><option value={640}>640</option></select></label><label className="training-field">Seed<input type="number" min={0} max={2147483647} value={parameters.seed} disabled={locked} onChange={(event) => change('seed', event.target.value)} /></label></div>
            </details>
            <p className="training-help">{unknown ? '训练服务尚未核实，不能创建运行。先取得远程操作授权并核实预留单卡；不抢占 KataGo。' : running ? `已有${view.designOnly ? '示例' : ''}运行，参数锁定。取消须等待本 run 进程退出；不会终止其他 GPU 进程。` : `${view.designOnly ? '配置仅用于设计演示；实际需' : '配置需'}固定根目录、可信本地权重与预留单卡，不允许隐式下载。`}</p>
            <button type="submit" className="training-button primary full" disabled={locked}>{unknown ? '创建运行 · 待授权' : running ? '已有运行 · 不并行启动' : `创建新运行${view.designOnly ? '（示意）' : ''}`}</button>
          </form>
        </section>
        <div>
          <section className="training-panel"><div className="training-panel-head"><h2>当前运行</h2><span className="training-status" data-status={view.state}><StatusIcon aria-hidden="true" />{statusLabel}{!unknown && view.designOnly ? ' · 示意' : ''}</span></div>
            {!run ? <div className="training-empty"><strong>尚未读取训练服务</strong><p>真实训练需要测试机数据集、可信权重和预留 GPU。没有核实结果时，不展示在线状态、日志或指标。</p></div> : <div className="training-run-body">
              <p className="training-run-id">{run.id}{view.designOnly ? ' · 设计示例' : ''}</p>
              <div className="training-progress-row"><strong>{completed ? '训练结束' : running ? `Epoch ${run.epoch} / ${run.totalEpochs}` : failed ? `在 Epoch ${run.epoch} 失败` : '已取消运行'}</strong><span>{completed ? `${run.epoch} / ${run.totalEpochs}` : running ? `${Math.round(run.epoch / run.totalEpochs * 100)}% · 等待后续 epoch` : failed ? '进度保留，未发布模型' : `进程已退出${view.designOnly ? '（示意）' : ''}`}</span></div>
              <progress value={run.epoch} max={run.totalEpochs} aria-label={view.designOnly ? '示例运行 epoch 进度' : '运行 epoch 进度'} />
              <dl className="training-metrics"><div><dt>mAP50</dt><dd>{metric(run.metrics.map50)}</dd></div><div><dt>Precision</dt><dd>{metric(run.metrics.precision)}</dd></div><div><dt>Recall</dt><dd>{metric(run.metrics.recall)}</dd></div></dl>
              <p className="training-help">{completed ? view.designOnly ? '设计指标示例，非实测。只在同 run 验证产物可读时展示。' : '只展示同 run 验证产物中的指标。' : '尚无可用验证指标；不填 0，不从其他 run 复制。'}</p>
              <div className="training-meta"><span>{run.gpu}</span><span>imgsz {run.parameters.imgsz} · batch {run.parameters.batch} · seed {run.parameters.seed}</span><span>数据集：{run.datasetId}</span></div>
              {failed && <div className="training-error" role="alert"><strong>{view.designOnly ? '示例错误：' : '错误：'}{run.error ?? '运行失败，尚无错误详情'}</strong>本 run 已退出；未发布新模型，旧版本保留。降低 Batch 后可创建新运行；不会自动重启。</div>}
              <div className="training-log-title"><strong>运行日志</strong><small>同一 run · 有界尾部{view.designOnly ? ' · 设计文本' : ''}</small></div>
              <pre className="training-log" aria-label="运行日志">{run.log.slice(-16000)}</pre>
              <div className="training-run-actions">{running ? <button className="training-button" type="button" onClick={onCancel}>取消此运行{view.designOnly ? '（示意）' : ''}</button> : failed ? <button className="training-button" type="button" onClick={onCreate}>按当前配置新建{view.designOnly ? '（示意）' : ''}</button> : null}</div>
            </div>}
          </section>
          <section className="training-panel training-models"><div className="training-panel-head"><h2>模型版本</h2><small>校验通过后只读保存</small></div>
            {models.length ? <table className="training-model-table" aria-label="模型版本"><thead><tr><th>版本 / 来源</th><th>类目 / 验证</th><th>Mac 获取</th></tr></thead><tbody>{models.map((model) => <tr key={model.id}><td>{model.id}<small>{model.runId}{view.designOnly ? ' · 示例' : ''}</small></td><td>{model.classNames.join(' · ')}<small>best.pt SHA256 {model.weightsSha256}{view.designOnly ? ' · 设计示意' : ''}</small></td><td><button className="training-button" type="button" disabled>下载 · 待授权</button></td></tr>)}</tbody></table> : <div className="training-model-empty">{unknown ? '尚未读取真实模型版本。' : `此${view.designOnly ? '示例' : ''}运行尚未发布模型；不会用 last.pt 冒充校验完成的 best.pt。`}</div>}
          </section>
        </div>
      </div>
      <p className="training-foot">只允许已冻结且清单校验一致的数据集。首版一次一运行、单 GPU；双卡 DDP 尚未验证。</p>
    </div>
    {pendingAction && <dialog ref={dialogRef} className="training-dialog" aria-label={`${pendingAction === 'cancel' ? '取消当前运行' : '创建单卡运行'}${view.designOnly ? '（设计演示）' : ''}`} onCancel={onDismiss}>
      <h2>{pendingAction === 'cancel' ? '取消当前运行' : '创建单卡运行'}{view.designOnly ? '（设计演示）' : ''}</h2>
      <p>{pendingAction === 'cancel' ? `仅停止 ${run?.id ?? '当前 run'} 的进程组，确认退出后才标为取消；真实操作不会影响 KataGo。${view.designOnly ? '此演示不调用任何服务。' : ''}` : `使用选中的冻结数据集与固定参数，首版只启动一个单卡运行。${view.designOnly ? '此演示只切换示例状态，不连接测试机或消耗 GPU。' : ''}`}</p>
      <div className="training-dialog-actions"><button type="button" className="training-button" onClick={onDismiss}>返回</button><button type="button" className="training-button primary" onClick={onConfirm}>{view.designOnly ? '确认设计操作' : '确认操作'}</button></div>
    </dialog>}
  </main>;
}
