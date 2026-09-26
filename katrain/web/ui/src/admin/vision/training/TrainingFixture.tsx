import { useState } from 'react';
import { BookOpen, Camera, Clock3 } from 'lucide-react';
import galaxyLogo from '../../../../../../img/logo-white.png';
import TrainingPage, { type TrainingParameters, type TrainingState, type TrainingView } from './TrainingPage';
import '../../AdminApp.css';

// All illustrative business data lives in this isolated controller, never the real admin entry.
const defaults: TrainingParameters = { epochs: 100, batch: 8, imgsz: 960, seed: 0 };
const states: TrainingState[] = ['unknown', 'running', 'failed', 'completed', 'cancelled'];
function fixtureView(state: TrainingState, parameters: TrainingParameters): TrainingView {
  if (state === 'unknown') return { state, designOnly: true, dataset: null, weights: null, augmentation: null, gpu: null, run: null, models: [] };
  const completed = state === 'completed';
  const failed = state === 'failed';
  const epoch = completed ? parameters.epochs : Math.min(12, parameters.epochs);
  const runId = 'run-demo-20260926';
  return {
    state, designOnly: true,
    dataset: { id: 'dataset-demo', label: '无灯双类 · 已冻结示例', classNames: ['black', 'white'], manifestSha256: 'demo…' },
    weights: 'YOLO11m · 示例', augmentation: '棋子标准 · 示例', gpu: 'GPU 0 · 预留单卡示例',
    run: {
      id: runId, epoch, totalEpochs: parameters.epochs, parameters: { ...parameters }, datasetId: 'dataset-demo', gpu: 'GPU 0 · 单卡示例',
      metrics: { map50: completed ? .92 : null, precision: completed ? .93 : null, recall: completed ? .90 : null },
      error: failed ? 'CUDA out of memory' : null,
      log: `[design-only] dataset manifest verified\n[design-only] local weights verified; no download\n[design-only] epoch ${Math.min(12, parameters.epochs)} / ${parameters.epochs}, imgsz=${parameters.imgsz}, batch=${parameters.batch}\n${failed ? '[design-only] CUDA out of memory; run failed' : completed ? `[design-only] epoch ${parameters.epochs}; best.pt + schema + manifest verified` : state === 'running' ? '[design-only] training; awaiting next observation' : '[design-only] run process exited after cancel'}`,
    },
    models: completed ? [{ id: 'model-demo-01', runId, classNames: ['black', 'white'], weightsSha256: 'demo…' }] : [],
  };
}

export default function TrainingFixture({ initialState }: { initialState?: TrainingState }) {
  const query = new URLSearchParams(window.location.search);
  const selectedState = query.get('state') as TrainingState;
  const [parameters, setParameters] = useState<TrainingParameters>(defaults);
  const [view, setView] = useState<TrainingView>(() => fixtureView(initialState ?? (states.includes(selectedState) ? selectedState : 'unknown'), defaults));
  const [theme, setTheme] = useState(query.get('theme') === 'light' ? 'light' : 'dark');
  const [pendingAction, setPendingAction] = useState<'create' | 'cancel' | null>(null);
  const capture = query.get('capture') === 'true';
  return <div className="admin-app admin-app-cron admin-training-fixture" data-theme={theme}>
    <header className="admin-top"><div className="admin-brand"><img src={galaxyLogo} alt="" /><span className="admin-brand-cn">智星盒</span><span className="admin-brand-en">StellaBox</span><span className="admin-brand-admin">管理后台</span></div><div className="admin-topright"><span className="admin-env">测试环境设计</span><span>admin:fan</span><span>退出</span></div></header>
    <div className="admin-wrap"><aside className="admin-side" aria-label="管理导航"><div className="admin-sidehead">内容与服务</div><span className="admin-nav"><BookOpen aria-hidden="true" />教程管理</span><span className="admin-nav"><Clock3 aria-hidden="true" />定时任务</span><span className="admin-nav active"><Camera aria-hidden="true" />视觉实验室</span><div className="admin-sidefoot">目标：home-ubuntu<br />服务与 GPU 未经核实；本稿不连接目标机。</div></aside>
      <TrainingPage view={view} parameters={parameters} pendingAction={pendingAction} onParametersChange={setParameters} onCreate={() => setPendingAction('create')} onCancel={() => setPendingAction('cancel')} onDismiss={() => setPendingAction(null)} onConfirm={() => {
        if (pendingAction) setView(fixtureView(pendingAction === 'cancel' ? 'cancelled' : 'running', parameters));
        setPendingAction(null);
      }} />
    </div>
    {!capture && <div className="training-tweaks" aria-label="Fixture 预览选项">{(['unknown', 'running', 'failed', 'completed'] as TrainingState[]).map((state) => <button className="training-button" key={state} type="button" onClick={() => { setPendingAction(null); setView(fixtureView(state, parameters)); }}>{({ unknown: '未核实', running: '运行中', failed: '失败', completed: '完成', cancelled: '已取消' })[state]}</button>)}<button className="training-button" type="button" onClick={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')}>深浅主题</button></div>}
  </div>;
}
