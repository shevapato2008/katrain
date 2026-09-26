import { useEffect, useState } from 'react';
import { Activity, Camera, CircleCheck, CircleHelp, Info, Lock, Play, RefreshCw, Square, TriangleAlert } from 'lucide-react';
import VisionDialog from '../VisionDialog';
import type { DiagnosticsSnapshot, DiagnosticsStage, DiagnosticsStatus, VisionModels, VisionStatus } from '../types';
import '../lab.css';
import './DiagnosticsPage.css';

const STAGES: { id: DiagnosticsStage['id']; title: string; short: string; tag: string; what: string; note: string }[] = [
  { id: 'raw', title: '原图 / 标定叠图', short: '原图', tag: '本轮锚点', what: '本轮处理批次的锚点原帧，叠加锁定几何的棋盘外框。不另取一张“最新图”。', note: '只用于核对标定是否贴合；模型不直接看这张图。' },
  { id: 'warped', title: '纯 warped', short: '纯 warped', tag: '平均前', what: '本轮原帧按锁定几何做透视校正，保留生产 margin。', note: '这是平均和增强之前的单帧，不是 YOLO 的实际输入。' },
  { id: 'nms', title: '模型 NMS 后框', short: 'NMS 后框', tag: '去重前', what: '底图是实际输入：多帧平均 + CLAHE。框是模型 NMS 之后、业务去重之前的全部检测。', note: '重复框与阴影误检会在下一阶段剔除。' },
  { id: 'filtered', title: '业务筛选后框', short: '筛选后框', tag: '去重后', what: '业务去重 + 阴影剔除后的框，分 keep / sustain 两档。', note: 'sustain 档只维持已有棋子，不单独产生新子；画出的框不等于全部参与赋值。' },
  { id: 'projection', title: '原始定位投影 · 诊断派生', short: '原始投影', tag: '诊断派生', what: '把筛选后框的原始连续网格坐标按最近点落格；越界丢弃，同格取最高置信度。', note: '不是生产中间结果：不做视差、历史、掩码修正，也不回灌状态。' },
  { id: 'assigned', title: '纠偏后棋盘', short: '纠偏后', tag: '实际赋值', what: '本轮唯一一次 detections_to_board() 的返回值，含视差修正和占位冲突处理。', note: '与上一阶段的差异就是纠偏逻辑的效果。' },
  { id: 'published', title: '最终发布棋盘', short: '最终发布', tag: '两帧稳定', what: '逐格两帧投票 → 否认掩码 → 参考检查之后实际发布的棋盘。', note: 'viewer 不绑定对局：参考检查与落子确认未参与，不产生第八张盘。' },
];
const LETTERS = 'ABCDEFGHJKLMNOPQRST';
const cell = (index: number) => `${LETTERS[index % 19]}${19 - Math.floor(index / 19)}`;
const stones = (board: string | null) => board ? [...board].filter((value) => value !== '0').length : 0;
const cells = (indices: number[]) => indices.length ? indices.slice(0, 8).map(cell).join('、') + (indices.length > 8 ? ` 等 ${indices.length} 格` : '') : '无';
const differ = (a: string | null, b: string | null) => a && b ? [...a].map((value, index) => (value !== b[index] ? index : -1)).filter((index) => index >= 0) : [];
const jpeg = (base64: string) => `data:image/jpeg;base64,${base64}`;
const BOX_COLORS = ['#5cc3ad', '#7fa9dc', '#ff8a80', '#7fe29a'];

function BoardView({ board, marks, color, label }: { board: string; marks: number[]; color: string; label: string }) {
  const at = (index: number) => [30 + (index % 19) * 30, 30 + Math.floor(index / 19) * 30];
  return <svg className="dg-board" viewBox="0 0 600 600" role="img" aria-label={label}>
    <rect width="600" height="600" fill="#d8c49b" />
    {Array.from({ length: 19 }, (_, i) => <g key={i}><line x1={30} x2={570} y1={30 + i * 30} y2={30 + i * 30} stroke="#5a4a32" strokeWidth="1" /><line y1={30} y2={570} x1={30 + i * 30} x2={30 + i * 30} stroke="#5a4a32" strokeWidth="1" /></g>)}
    {[3, 9, 15].flatMap((r) => [3, 9, 15].map((c) => <circle key={`h${r}${c}`} cx={30 + c * 30} cy={30 + r * 30} r={3} fill="#5a4a32" />))}
    {[...board].map((value, index) => {
      if (value === '0') return null;
      const [x, y] = at(index);
      return <circle key={index} cx={x} cy={y} r={13.5} fill={value === '1' ? '#1e1f22' : '#f5f2ea'} stroke={value === '1' ? '#0b0b0c' : '#8f8878'} />;
    })}
    {marks.map((index) => { const [x, y] = at(index); return <rect key={`m${index}`} x={x - 16} y={y - 16} width={32} height={32} fill="none" stroke={color} strokeWidth="3" />; })}
  </svg>;
}

type Props = {
  capture: VisionStatus | null; models: VisionModels | null; status: DiagnosticsStatus | null; snapshot: DiagnosticsSnapshot | null;
  busy: string; error: string; authorized: boolean;
  onRefresh: () => void; onActivate: (id: string) => void; onRollback: () => void; onStart: () => void; onStop: () => void; onCapturePage: () => void;
};

export default function DiagnosticsPage(props: Props) {
  const { capture, models, status, snapshot, busy, error } = props;
  const [stage, setStage] = useState(0);
  const [selected, setSelected] = useState('');
  const [confirm, setConfirm] = useState<null | 'start' | 'activate' | 'rollback'>(null);
  const [checked, setChecked] = useState(false);
  const deviceReady = capture?.camera.state === 'connected' && capture.geometry.state === 'ready';
  const running = status?.state === 'running' || status?.state === 'stopping';
  const stale = running && !!snapshot?.stale;
  const loaded = models?.models.find((item) => item.id === models.loaded_id);
  const valid = models?.models.filter((item) => item.valid) ?? [];
  const choice = selected || models?.current || valid[0]?.id || '';
  const locked = !!busy || !props.authorized;
  const short = (id?: string | null) => id ? id.slice(6, 18) : '—';
  const headline = status?.state === 'error' ? ['诊断出错 · 已停', 'warn', TriangleAlert] as const
    : status?.state === 'stopping' ? ['正在停止 · 等待线程退出', 'warn', TriangleAlert] as const
      : stale ? ['快照陈旧', 'warn', TriangleAlert] as const
        : running ? ['诊断中 · ≤2 Hz', 'ok', Activity] as const
          : !capture ? ['正在读取', '', CircleHelp] as const
            : deviceReady ? ['设备就绪 · 未开始', 'ok', CircleCheck] as const : ['未连接 · 未核实', '', CircleHelp] as const;
  const Icon = headline[2];
  const info = STAGES[stage];
  const current = snapshot?.stages.find((item) => item.id === info.id);
  const boards = Object.fromEntries((snapshot?.stages ?? []).map((item) => [item.id, item.board])) as Record<string, string | null>;
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (confirm || (event.target as HTMLElement)?.closest?.('input,select,textarea')) return;
      if (/^[1-7]$/.test(event.key)) setStage(Number(event.key) - 1);
      else if (event.key === 'ArrowRight') setStage((value) => Math.min(6, value + 1));
      else if (event.key === 'ArrowLeft') setStage((value) => Math.max(0, value - 1));
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [confirm]);

  const facts = (): [string, string][] => {
    if (!snapshot || !current) return [];
    const nms = snapshot.stages[2].boxes; const filtered = snapshot.stages[3].boxes;
    const count = (boxes: typeof nms, cls: number) => boxes?.filter((box) => box.class_id === cls).length ?? 0;
    const names = snapshot.class_names ?? [];
    switch (info.id) {
      case 'raw': return [['原帧', `相机帧 #${snapshot.camera_seq ?? '—'} · ${snapshot.images.raw.width}×${snapshot.images.raw.height}（已缩放）`], ['几何', `${snapshot.geometry_revision?.slice(0, 12) ?? '—'} · 锁定外框`], ['与上一阶段', '—（批次锚点）']];
      case 'warped': return [['尺寸', `${snapshot.images.warped.width}×${snapshot.images.warped.height} · 含 margin`], ['来源', '同一原帧，未平均'], ['与上一阶段', '仅做透视校正']];
      case 'nms': return nms ? [['检测框', `${nms.length} 个 · ${names.map((name, index) => `${name} ${count(nms, index)}`).join(' · ')}`], ['贡献帧', `${snapshot.contributor_count} 帧${snapshot.contributors.length ? ` · #${snapshot.contributors[0]} … #${snapshot.contributors[snapshot.contributors.length - 1]}` : ''}`], ['与上一阶段', '换成平均 + CLAHE 底图']] : [['不可用', current.unavailable ?? '—']];
      case 'filtered': return filtered ? [['保留框', `${filtered.length} 个 · keep ${filtered.filter((box) => box.tier === 'keep').length} · sustain ${filtered.filter((box) => box.tier === 'sustain').length} · 低于 keep ${filtered.filter((box) => box.tier === 'below').length}`], ['剔除', nms ? `${nms.length - filtered.length} 个（重复框 + 阴影）` : '—'], ['与上一阶段', '业务去重与阴影剔除']] : [['不可用', current.unavailable ?? '—']];
      case 'projection': return [['落格棋子', `${stones(boards.projection)} 子`], ['与纠偏后', `${differ(boards.projection, boards.assigned).length} 格不同（红框）：${cells(differ(boards.projection, boards.assigned))}`]];
      case 'assigned': return [['棋子', `${stones(boards.assigned)} 子`], ['与原始投影', `${differ(boards.projection, boards.assigned).length} 格差异（绿框）`]];
      default: return [['发布棋子', `${stones(boards.published)} 子`], ['与纠偏后', `${differ(boards.assigned, boards.published).length} 格未稳定或被否认（橙框）：${cells(differ(boards.assigned, boards.published))}`], ['参考检查', snapshot.reference_participates ? `参与 · ${snapshot.reference_mode}` : 'viewer 未参与']];
    }
  };
  const viewer = () => {
    if (!running || !snapshot) return <div className="lab-empty">{deviceReady ? <Camera aria-hidden="true" /> : <CircleHelp aria-hidden="true" />}<span>{!running ? (deviceReady ? '等待显式开始诊断' : '尚无已核实快照') : '正在等待第一个处理批次'}</span><small>{info.title}</small></div>;
    if (current?.board) {
      // Mark where this stage disagrees with its neighbour: a stone it has there, or (published) a stone it lost.
      const own = (board: string | null, other: string | null) => differ(board, other).filter((index) => board?.[index] !== '0');
      const marks = info.id === 'projection' ? own(boards.projection, boards.assigned) : info.id === 'assigned' ? own(boards.assigned, boards.projection) : differ(boards.assigned, boards.published);
      const color = info.id === 'projection' ? '#d14b3f' : info.id === 'assigned' ? '#2f9c86' : '#e39a3a';
      return <div className="dg-square"><BoardView board={current.board} marks={marks} color={color} label={info.title} /></div>;
    }
    const image = current?.image ? snapshot.images[current.image] : null;
    if (!image || !current) return <div className="lab-empty"><Info aria-hidden="true" /><span>本阶段不可用</span><small>{current?.unavailable}</small></div>;
    return <div className="dg-figure" style={{ aspectRatio: `${image.width} / ${image.height}` }}>
      <img src={jpeg(image.jpeg_base64)} alt={info.title} />
      {current.boxes && <svg className="dg-boxes" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">{current.boxes.map((box, index) => <rect key={index} x={box.x1 * 1000} y={box.y1 * 1000} width={(box.x2 - box.x1) * 1000} height={(box.y2 - box.y1) * 1000} fill="none" stroke={box.tier === 'sustain' ? '#f1c07c' : box.tier === 'below' ? '#9c9a96' : BOX_COLORS[box.class_id] ?? '#fff'} strokeWidth="3" vectorEffect="non-scaling-stroke" />)}</svg>}
      {!current.boxes && current.unavailable && <span className="lab-tag dg-warn">{current.unavailable}</span>}
    </div>;
  };

  return <main className="lab-page dg-page">
    <div className="lab-heading"><div><h1>本机部署与诊断</h1><p>Mac 本机 · 可信模型与识别链七阶段观察</p></div><div className={`lab-status ${headline[1]}`}><Icon aria-hidden="true" />{busy ? `${busy}…` : headline[0]}<button className="lab-btn small ghost" type="button" aria-label="刷新诊断状态" disabled={locked} onClick={props.onRefresh}><RefreshCw aria-hidden="true" /></button></div></div>
    <div className="lab-content">
      {error && <div className="lab-banner bad" role="alert"><TriangleAlert aria-hidden="true" /><span>{error}</span></div>}
      {capture && !capture.enabled && <div className="lab-banner info"><Info aria-hidden="true" /><span>此服务未启用本机视觉控制；不会远程打开 Mac 摄像头或加载模型。</span></div>}
      <section className="lab-panel dg-controls" aria-label="本机模型与诊断控制">
        <div className="dg-model-row">
          <div className="dg-version"><small>当前本机版本</small><strong>{models ? short(models.current) : '尚未读取'}</strong></div>
          <div className="dg-version"><small>前一版本 · 保留</small><strong>{models ? short(models.previous) : '尚未读取'}</strong></div>
          <label className="dg-registered">登记模型<select value={choice} disabled={locked || running || !valid.length} onChange={(event) => setSelected(event.target.value)} aria-describedby="dg-lock">{valid.length ? valid.map((item) => <option key={item.id} value={item.id}>{short(item.id)} · {item.mode === 'led4' ? '四类' : '双类'} · imgsz {item.parameters?.imgsz ?? '—'}</option>) : <option value="">尚无已核实的本机模型</option>}</select></label>
          <button className="lab-btn" type="button" disabled={locked || running || !choice} onClick={() => { setConfirm('activate'); setChecked(false); }} aria-describedby="dg-lock">激活</button>
          <button className="lab-btn" type="button" disabled={locked || running || !models?.previous} onClick={() => { setConfirm('rollback'); setChecked(false); }} aria-describedby="dg-lock">回滚</button>
          <button className="lab-btn" type="button" disabled>从测试机拉取 · 待授权</button>
        </div>
        <div className="dg-run-row">
          <div className="dg-meta">{loaded ? <><span>manifest <strong>{loaded.manifest_sha256?.slice(0, 12)}</strong></span><span>imgsz <strong>{loaded.parameters?.imgsz ?? '—'}</strong></span><span>类目 <strong>{loaded.class_names?.map((name, index) => `${name} ${index}`).join(' · ')}</strong></span><span>viewer · 不绑定对局</span></> : models?.current ? <span>当前版本 <strong>未加载</strong> · 点「激活」核对并加载</span> : <span>模型 manifest / 实际 imgsz / 类目：<strong>{models?.models.length ? '未加载' : '本机没有登记模型'}</strong></span>}{running && <span className="dg-lock" id="dg-lock"><Lock aria-hidden="true" />诊断未停止 · 换模前请先停止</span>}</div>
          <button className="lab-btn primary" type="button" disabled={locked || running || !deviceReady || !loaded} onClick={() => { setConfirm('start'); setChecked(false); }}><Play aria-hidden="true" />{!deviceReady ? '开始诊断 · 设备未就绪' : !loaded ? '开始诊断 · 未加载模型' : '开始诊断'}</button>
          <button className="lab-btn" type="button" disabled={locked || !running} onClick={props.onStop}><Square aria-hidden="true" />停止诊断</button>
        </div>
      </section>
      {models?.load_error && <div className="lab-banner" role="alert"><TriangleAlert aria-hidden="true" /><span><strong>模型加载失败 · 诊断已停</strong> {models.load_error}。当前与前一版保留不变；核实登记模型后重试。</span></div>}
      {status?.error && <div className="lab-banner bad" role="alert"><TriangleAlert aria-hidden="true" /><span>{status.error}</span></div>}
      {stale && <div className="lab-banner" role="alert"><TriangleAlert aria-hidden="true" /><span><strong>整份旧快照 · {snapshot?.age_s.toFixed(0)} 秒未更新</strong> 画面可能在动或设备断开；七个阶段仍来自同一旧批次，不拼接新原图与旧棋盘。</span></div>}
      {capture?.enabled && !deviceReady && <div className="lab-banner info"><Info aria-hidden="true" /><span>相机与标定由「采集与数据集」显式准备；这里不会自动打开设备。</span><button className="lab-btn small" type="button" onClick={props.onCapturePage}>去连接与标定</button></div>}
      <section className="lab-panel" aria-label="七个处理阶段">
        <div className="lab-tabs" role="tablist">{STAGES.map((item, index) => <button key={item.id} type="button" role="tab" className="lab-tab" aria-selected={index === stage} onClick={() => setStage(index)}><b className="dg-num">0{index + 1}</b>{item.short}</button>)}</div>
        <div className="dg-stage">
          <div className="lab-viewer dg-viewer">{viewer()}{running && snapshot && <><span className="lab-tag">0{stage + 1} · {info.title}</span>{info.id === 'filtered' && <span className="lab-legend"><span style={{ color: '#5cc3ad' }}>keep</span><span style={{ color: '#f1c07c' }}>sustain</span></span>}</>}</div>
          <aside className="dg-side">
            <div className={`dg-batch ${stale ? 'stale' : ''}`} aria-label="共享处理批次">{running && snapshot ? <div><strong>同一处理批次 · {snapshot.batch_id}</strong><p>相机帧 #{snapshot.camera_seq ?? '—'} · 几何 {snapshot.geometry_revision?.slice(0, 8)} · 模型 {short(snapshot.model_id)} · 观察 {new Date(snapshot.observed_at).toLocaleTimeString('zh-CN', { hour12: false })}</p></div> : <div><strong>{deviceReady ? '尚无诊断批次' : '没有可核实的处理批次'}</strong><p>{deviceReady ? '确认后显式开始；七个阶段来自同一次真实识别。' : '设备、几何与模型未核实；不展示画面。'}</p></div>}
              <details><summary>批次来源与边界</summary><div className="dg-pop">原图与纯 warp 锚定本轮帧，第 3、4 阶段用平均 + CLAHE 的实际输入。模型、几何与帧身份同轮保存，不再次推理。<br /><strong>资源上限</strong>：底图 ≤3、长边 ≤960、每张 JPEG ≤1 MiB、每阶段 ≤4096 框、总响应 ≤8 MiB；超限报不可用，不裁剪冒充完整。</div></details></div>
            <div><div className="dg-kicker">阶段 {stage + 1} / 7 · {info.tag}</div><h3>{info.title}</h3></div>
            <dl><div><dt>这是什么</dt><dd>{info.what}</dd></div>{facts().map(([key, value]) => <div key={key}><dt>{key}</dt><dd>{value}</dd></div>)}<div><dt>注意</dt><dd>{info.note}</dd></div></dl>
            <div className="lab-row"><button className="lab-btn small" type="button" disabled={!stage} onClick={() => setStage(stage - 1)}>← 上一阶段</button><button className="lab-btn small" type="button" disabled={stage === 6} onClick={() => setStage(stage + 1)}>下一阶段 →</button></div>
            <div className="dg-keys">键盘 1–7 直接切换，←/→ 前后切换</div>
          </aside>
        </div>
      </section>
      <p className="lab-foot">viewer 只读观察 · 一次真实推理链、最多 2 Hz 展示 · 不绑定对局，不启 monitor，不提交棋步或驱动指示灯。切换设备、标定或模型前先停止并确认旧线程退出。</p>
    </div>
    {confirm && <VisionDialog title={confirm === 'start' ? '开始只读诊断' : confirm === 'activate' ? '激活登记模型' : '回滚本机模型'} onClose={() => setConfirm(null)}>
      <div className="vision-review-body">
        <p>{confirm === 'start' ? `使用当前摄像头、锁定几何与本机模型 ${short(models?.loaded_id)}，只开 viewer。` : confirm === 'activate' ? `激活 ${short(choice)}：核对权重 SHA-256、类目顺序与 imgsz 后加载。加载成功才替换当前版；失败保留当前与前一版。` : `回滚到 ${short(models?.previous)}：同样核对产物后加载；失败保留当前版。`}</p>
        <label className="vision-check"><input type="checkbox" checked={checked} onChange={(event) => setChecked(event.target.checked)} />{confirm === 'start' ? '我已理解 viewer 不参与对局、参考检查与落子确认。' : '我理解加载失败不会替换当前版本。'}</label>
      </div>
      <div className="vision-review-foot"><span /><button className="vision-button" type="button" disabled={!checked || locked} onClick={() => { const kind = confirm; setConfirm(null); if (kind === 'start') props.onStart(); else if (kind === 'activate') props.onActivate(choice); else props.onRollback(); }}>{confirm === 'start' ? '确认开始' : confirm === 'activate' ? '确认激活' : '确认回滚'}</button></div>
    </VisionDialog>}
  </main>;
}
