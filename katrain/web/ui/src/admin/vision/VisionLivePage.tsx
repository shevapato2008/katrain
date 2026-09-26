import { useEffect, useRef, useState } from 'react';
import { Activity, Camera, Info, RefreshCw } from 'lucide-react';
import VisionDialog from './VisionDialog';
import type { VisionDevices, VisionFrozen, VisionMode, VisionPreview, VisionReviewFailure, VisionSampleReview, VisionSession, VisionSessionList, VisionStatus, VisionStep } from './types';
import './VisionCapturePage.css';

type Props = {
  status: VisionStatus | null; devices: VisionDevices['candidates']; sessions: VisionSessionList | null;
  session: VisionSession | null; preview: VisionPreview | null; review: VisionSampleReview | null;
  frozen: VisionFrozen | null; busy: string; error: string; previewError: string; message: string; authorized: boolean;
  reviewFailure: VisionReviewFailure | null; contextVersion: number;
  onRefresh: () => void; onConnect: (id: number, mode: VisionMode) => void; onDisconnect: () => void;
  onCalibrate: () => void; onImport: (sgf: string, expectedStatus: VisionStatus, expectedContext: number) => void; onResume: (id: string) => void;
  onVerify: (frame: string) => void; onPausePreview: (paused: boolean) => void;
  onCapture: (index: number, retake?: boolean) => void; onReview: (frame: string) => void;
  onCloseReview: () => void; onFreeze: () => void;
  onTraining?: () => void;
};
const modeLabel = (mode?: VisionMode | null) => mode === 'led4' ? 'LED 四类' : mode === 'stones2' ? '无灯双类' : '模式未选择';
const coordinate = (step: VisionStep) => step.col !== null && step.row !== null ? `${'ABCDEFGHJKLMNOPQRST'[step.col]}${19 - step.row}` : '';
const stepLabel = (index: number, steps: VisionStep[]) => {
  if (index === -1) return '初始空盘';
  const step = steps.find((item) => item.move_index === index);
  return step ? `第 ${index + 1} 手 · ${step.color === 'B' ? '黑棋' : '白棋'} ${coordinate(step)}${step.kind === 'setup' ? '（摆子）' : ''}` : `第 ${index + 1} 手`;
};
const jpeg = (base64?: string | null) => base64 ? `data:image/jpeg;base64,${base64}` : undefined;
const readFile = (file: File, reader: FileReader) => new Promise<string>((resolve, reject) => {
  reader.onload = () => resolve(String(reader.result));
  reader.onerror = () => reject(new Error('无法读取 SGF 文件。'));
  reader.onabort = () => reject(new DOMException('File read cancelled', 'AbortError'));
  reader.readAsText(file, 'UTF-8');
});

export default function VisionLivePage(props: Props) {
  const { status, devices, sessions, session, preview, review, reviewFailure, frozen, busy, error, previewError, message, authorized } = props;
  const [device, setDevice] = useState(0);
  const [mode, setMode] = useState<VisionMode>('stones2');
  const [emptyConfirmed, setEmptyConfirmed] = useState('');
  const [boardConfirmed, setBoardConfirmed] = useState('');
  const [geometryConfirmed, setGeometryConfirmed] = useState('');
  const [grid, setGrid] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [readingFile, setReadingFile] = useState(false);
  const [chooseNew, setChooseNew] = useState(false);
  const [resumeOpen, setResumeOpen] = useState(false);
  const [resumeId, setResumeId] = useState('');
  const [retakeConfirmed, setRetakeConfirmed] = useState('');
  const [retakeBoardConfirmed, setRetakeBoardConfirmed] = useState('');
  const [needsNewSession, setNeedsNewSession] = useState('');
  const fileReader = useRef<FileReader | null>(null);
  const enabled = !!status?.enabled && authorized;
  const connected = status?.camera.state === 'connected';
  const ready = connected && status?.geometry.state === 'ready' && !error && !previewError;
  const locked = !!busy || readingFile || !enabled;
  const cameraState = status?.camera.state ?? 'unknown';
  const cameraText = !status ? '正在读取本机状态' : connected ? '本机摄像头已连接' : cameraState === 'connecting' ? '正在连接摄像头' : cameraState === 'occupied' ? '摄像头被其他进程占用' : cameraState === 'error' ? '摄像头连接失败' : '尚未连接本机摄像头';
  const geometryKey = `${status?.camera.device_id}/${status?.mode}/${status?.geometry.revision}`;
  const boardKey = `${session?.game_id}/${status?.sgf.next_step}/${status?.dataset.count}/${status?.geometry.state}/${geometryKey}`;
  const inspected = review ?? reviewFailure?.frame;
  const inspectedSha = review?.source_sha256 ?? reviewFailure?.frame.sha256;
  const reviewKey = inspected ? `${inspected.frame_id}/${inspectedSha}/${session?.game_id}` : '';
  const next = status?.sgf.next_step;
  const steps = session?.steps ?? [];
  const frames = session?.frames ?? [];
  const raw = preview && connected ? jpeg(grid ? preview.geometry_overlay_jpeg_base64 ?? preview.raw_jpeg_base64 : preview.raw_jpeg_base64) : undefined;
  const warp = preview && connected ? jpeg(preview.warped_jpeg_base64) : undefined;
  const skippedPasses = steps.filter((step) => step.kind === 'pass').length;
  const frozenId = frozen?.id ?? (status?.dataset.state === 'frozen' ? status.dataset.id : null);
  const geometryChanged = session?.state === 'captured' && session.geometry_revision !== status?.geometry.revision;
  const savedCamera = session?.camera_device_id ?? frames[0]?.capture_condition?.camera_device_id;
  const sessionMismatch = !!session && connected && (session.mode !== status.mode || (savedCamera !== undefined && savedCamera !== status.camera.device_id));
  const captureReady = ready && !geometryChanged && !sessionMismatch && session?.game_id !== needsNewSession;
  const fileContext = `${props.contextVersion}/${cameraState}/${enabled}/${geometryKey}/${session?.game_id}/${next}/${status?.dataset.count}`;
  useEffect(() => () => {
    const reader = fileReader.current; fileReader.current = null; reader?.abort();
  }, [fileContext]);

  async function importFile() {
    if (!file || locked || !ready || !status) return;
    setReadingFile(true); setFileError('');
    const reader = new FileReader(); fileReader.current = reader;
    try {
      const text = await readFile(file, reader);
      if (fileReader.current !== reader) return;
      fileReader.current = null; props.onImport(text, status, props.contextVersion); setChooseNew(false);
    }
    catch (cause) { if (!(cause instanceof DOMException && cause.name === 'AbortError')) setFileError(cause instanceof Error ? cause.message : '无法读取 SGF。'); }
    finally { setReadingFile(false); }
  }

  return <main className="vision-capture-page vision-live-page" data-camera={cameraState}>
    <div className="vision-heading"><div><h1>视觉实验室</h1><p>Mac 本机 · 摆谱采集与数据集</p></div><div className="vision-location"><Camera aria-hidden="true" />{cameraText}<button className="vision-button" type="button" disabled={!!busy || !authorized} onClick={props.onRefresh} aria-label="刷新本机状态"><RefreshCw aria-hidden="true" /></button></div></div>
    <div className="vision-content">
      {status && !status.enabled && <p className="vision-nonlocal"><Info aria-hidden="true" />此服务未启用本机视觉控制；不会远程打开 Mac 摄像头。</p>}
      {(error || fileError) && <div className="vision-feedback" role="alert">{error || fileError}<button type="button" className="vision-retry" onClick={props.onRefresh} disabled={!!busy}><RefreshCw aria-hidden="true" />重试读取状态</button></div>}
      {message && <p className="vision-feedback" role="status">{message}</p>}
      <nav className="vision-steps" aria-label="视觉实验室流程"><span className="vision-step active"><b>1</b>采集与数据集</span><span className="vision-separator" />{props.onTraining ? <button className="vision-step" style={{ border: 0, padding: 0, background: 'none', color: 'inherit', font: 'inherit', cursor: 'pointer' }} type="button" disabled={!!busy} onClick={props.onTraining}><b>2</b>训练与模型</button> : <span className="vision-step"><b>2</b>训练与模型</span>}<span className="vision-separator" /><span className="vision-step"><b>3</b>本机部署与诊断</span></nav>
      <div className="vision-grid">
        <section className="vision-preview" aria-label="采集预览"><div className="vision-panel-head"><h2>采集预览</h2><span>同一帧 · 原图 / 校正图</span></div>
          <div className="vision-streams">
            <div className="vision-stream"><div className="vision-stream-label"><strong>原始相机画面</strong><span>{preview ? `帧 ${preview.camera_seq}` : '等待实际画面'}</span></div><div className="vision-stream-frame">{raw ? <img src={raw} alt="原始相机画面" /> : <div className="vision-stream-empty"><Camera aria-hidden="true" /><span>{connected ? '等待新鲜相机帧' : '尚未连接本机摄像头'}</span><small>仅在 Mac 后台显式连接</small></div>}</div><div className="vision-stream-footer">不加视觉变形 · 不上传预览</div></div>
            <div className="vision-stream"><div className="vision-stream-label"><strong>warped 画面</strong><span>共享帧与标定版本</span></div><div className="vision-stream-frame">{warp ? <img src={warp} alt="标定后的画面" /> : <div className="vision-stream-empty"><Activity aria-hidden="true" /><span>{status?.geometry.state === 'required' ? '等待空盘标定' : '等待同帧校正画面'}</span><small>未标定时不生成校正画面</small></div>}</div><div className="vision-stream-footer">{preview?.geometry_revision ? `几何 ${preview.geometry_revision.slice(0, 12)}` : '无已验证几何'} · 同一帧检查</div></div>
          </div><div className="vision-preview-toolbar"><label className="vision-check"><input type="checkbox" checked={grid} onChange={(event) => { setGrid(event.target.checked); if (!event.target.checked) { setGeometryConfirmed(''); props.onPausePreview(false); } }} />显示标定网格</label><span>预览最多 2 帧/秒 · 非训练视频</span></div>
          {previewError && <p className="vision-preview-error" role="alert">{previewError}</p>}
          <div className="vision-preview-foot">采集前摆好当前棋面并明确确认；SGF 是落子与提子的真值。</div>
        </section>
        <aside className="vision-controls" aria-label="采集步骤"><div className="vision-panel-head"><h2>采集步骤</h2><span>{busy ? `${busy}…` : '按顺序完成'}</span></div><div className="vision-controls-body">
          <section className="vision-control-group"><div className="vision-control-label"><b>1</b>连接本机摄像头</div>
            {connected ? <div className="vision-connected-row"><span>Camera {status.camera.device_id} · {modeLabel(status.mode)}</span><button className="vision-button" type="button" disabled={locked} onClick={props.onDisconnect}>断开连接</button></div> : <>
              <div className="vision-row"><label className="vision-field">摄像头<select value={device} disabled={locked || !devices.length} onChange={(event) => setDevice(Number(event.target.value))}>{devices.length ? devices.map((item) => <option key={item.device_id} value={item.device_id}>{item.label} · 待尝试</option>) : <option value={0}>尚未读取设备候选</option>}</select></label><label className="vision-field">采集模式<select value={mode} disabled={locked} onChange={(event) => setMode(event.target.value as VisionMode)}><option value="stones2">无灯 · 双类棋子</option><option value="led4">LED · 四类</option></select></label></div>
              <p className="vision-status-note">设备候选不等于可用；占用时不会抢占。</p><button className="vision-button" type="button" disabled={locked || !devices.length} onClick={() => props.onConnect(device, mode)}>连接摄像头</button>
            </>}
            {status?.camera.error && <p className="vision-control-error" role="alert">{status.camera.error}</p>}
            {status?.led.error && <p className="vision-control-error" role="alert">LED：{status.led.error}</p>}
          </section>
          <section className="vision-control-group"><div className="vision-control-label"><b>2</b>空盘标定</div>
            {status?.geometry.state === 'stale' ? <>
              <p>恢复的几何待复核；重连不代表视角未变。</p>
              <label className="vision-check"><input type="checkbox" disabled={locked || !connected || sessionMismatch || !grid || !preview?.geometry_overlay_jpeg_base64 || preview.geometry_revision !== status.geometry.revision} checked={!!preview && geometryConfirmed === preview.frame_id} onChange={(event) => { setGeometryConfirmed(event.target.checked ? preview?.frame_id ?? '' : ''); props.onPausePreview(event.target.checked); }} />已检查当前网格，视角与原标定一致</label>
              <button className="vision-button" type="button" disabled={locked || !connected || sessionMismatch || !grid || !preview || geometryConfirmed !== preview.frame_id} onClick={() => { if (preview) props.onVerify(preview.frame_id); setGeometryConfirmed(''); }}>确认保存的标定</button>
              <p className="vision-status-note">视角已变化？清空棋盘后新建标定，再导入新 SGF 会话；不覆盖原会话。</p>
            </> : <p className="vision-status-note">{!connected ? '连接后清空棋子再标定。' : ready ? `标定通过 · ${status?.geometry.source ?? '已保存几何'}` : '等待空盘标定'}</p>}
            <label className="vision-check"><input type="checkbox" checked={emptyConfirmed === geometryKey} disabled={locked || !connected} onChange={(event) => setEmptyConfirmed(event.target.checked ? geometryKey : '')} />{ready ? '棋盘已清空，需要重新标定' : '棋盘已清空，可开始标定'}</label>
            <button className="vision-button" type="button" disabled={locked || !connected || emptyConfirmed !== geometryKey} onClick={() => { setEmptyConfirmed(''); setBoardConfirmed(''); if (session?.frames.length) { setNeedsNewSession(session.game_id); setChooseNew(true); setFile(null); } props.onCalibrate(); }}>{ready || status?.geometry.state === 'stale' ? '重新空盘标定' : '开始空盘标定'}</button>
            {status?.geometry.error && <p className="vision-control-error" role="alert">{status.geometry.error}</p>}
          </section>
          <section className="vision-control-group"><div className="vision-control-label"><b>3</b>导入或恢复棋谱</div>
            {(!session || chooseNew) && <label className="vision-field">SGF 文件<input type="file" accept=".sgf" disabled={locked} onChange={(event) => {
              const selected = event.target.files?.[0] ?? null;
              setFile(selected && selected.size <= 2 * 1024 * 1024 ? selected : null);
              setFileError(selected && selected.size > 2 * 1024 * 1024 ? 'SGF 文件不能超过 2 MiB。' : '');
            }} /></label>}
            <div className="vision-row vision-session-actions">{session && !chooseNew ? <button className="vision-button" type="button" disabled={locked} onClick={() => { setChooseNew(true); setFile(null); }}>选择新棋谱</button> : <button className="vision-button" type="button" disabled={locked || !file || !ready} onClick={() => { void importFile(); }}>导入新会话</button>}<button className="vision-button" type="button" disabled={locked || !sessions} onClick={() => setResumeOpen(true)}>恢复会话</button></div>
            {session && <div className="vision-session-line">{session.game_id.slice(0, 12)} · {frames.length} 张样本 · {steps.length} 个 SGF 步骤{skippedPasses > 0 && `（${skippedPasses} 次停着不采帧）`}</div>}
            {sessionMismatch && <p className="vision-control-error" role="alert">当前设备或模式与原会话不同；请断开后选择 {savedCamera === undefined ? '原摄像头' : `Camera ${savedCamera}`} · {modeLabel(session?.mode)}，或标定并导入新会话。</p>}
          </section>
          <section className="vision-control-group"><div className="vision-control-label"><b>4</b>逐手采集</div>
            <strong className="vision-next">{geometryChanged || session?.game_id === needsNewSession ? '视角已重新标定，请导入新会话' : !session ? '先连接、标定并导入棋谱' : next === -1 ? '下一帧：初始空盘' : next === null ? '棋谱采集已完成' : `下一手：${stepLabel(next ?? -1, steps)}`}</strong>
            <p>{next === -1 ? '清空棋盘，保存真实负样本；随后按 SGF 摆谱。' : '先按 SGF 摆好棋面；如有提子，也须移除。'}</p>
            <label className="vision-check"><input type="checkbox" checked={boardConfirmed === boardKey} disabled={locked || !captureReady || !session || next === null} onChange={(event) => setBoardConfirmed(event.target.checked ? boardKey : '')} />已摆放并核对当前棋面</label>
            <button className="vision-button primary" type="button" disabled={locked || !captureReady || !session || next === null || next === undefined || boardConfirmed !== boardKey} onClick={() => { if (next !== null && next !== undefined) props.onCapture(next); setBoardConfirmed(''); }}>确认并采集</button>
          </section>
        </div></aside>
      </div>
      <section className="vision-dataset" aria-label="数据集草稿"><div className="vision-panel-head"><h2>数据集草稿</h2><span>检查叠框 → 冻结版本 → 待上传</span></div><div className="vision-dataset-body"><div className="vision-dataset-copy"><strong>{frames.length ? `${frames.length} 张样本 · ${modeLabel(session?.mode)} · ${frozenId ? '已冻结' : '尚未冻结'}` : '还没有采集样本'}</strong><p>训练/验证按 SGF 时间段划分；冻结版本只读，失败保留原文件。</p>{frozenId && <div className="vision-session-line">版本 {frozenId}{frozen && <> · 清单 SHA256 {frozen.manifest_sha256.slice(0, 16)}</>}</div>}</div><div className="vision-dataset-actions"><button className="vision-button" type="button" disabled={locked || !frames.length} onClick={() => { const last = frames.at(-1); if (last) props.onReview(last.frame_id); }}>检查样本</button><button className="vision-button" type="button" disabled={locked || frames.length < 2} onClick={props.onFreeze}>{busy === '冻结数据集' ? '正在冻结…' : '冻结版本'}</button><button className="vision-button" type="button" disabled>上传测试环境 · 待授权</button></div>
        {!!frames.length && <div className="vision-samples" aria-label="已采集样本">{frames.map((frame) => <button key={frame.frame_id} className="vision-sample" type="button" disabled={locked} onClick={() => props.onReview(frame.frame_id)}>{stepLabel(frame.applied_move_index, steps)}<small>{frame.frame_id.slice(0, 10)} · 查看标签</small></button>)}</div>}
      </div></section>
      <p className="vision-local-note">相机与训练帧仅在本机；离开页面不会断开设备，请手动断开。冻结为同步操作，请等待校验完成。</p>
    </div>
    {resumeOpen && <VisionDialog title="恢复采集会话" onClose={() => setResumeOpen(false)}><div className="vision-review-body">{sessions?.sessions.length ? <label className="vision-field">保存的会话<select value={resumeId} onChange={(event) => setResumeId(event.target.value)}><option value="">选择会话</option>{sessions.sessions.map((item) => <option key={item.game_id} value={item.game_id} disabled={item.state === 'error'}>{item.game_id.slice(0, 12)} · {item.count ?? 0} 张 · {item.state === 'error' ? `错误：${item.error}` : modeLabel(item.mode)}</option>)}</select></label> : <p>本机没有保存的采集会话。</p>}<p className="vision-status-note">恢复不会自动切换设备或模式；已保存几何须对照当前网格重新确认。</p>{sessions?.truncated && <p>仅显示前 {sessions.limit} 个会话。</p>}</div><div className="vision-review-foot"><span>原会话的几何与样本保持不变。</span><button className="vision-button" type="button" disabled={locked || !resumeId} onClick={() => { props.onResume(resumeId); setResumeOpen(false); setBoardConfirmed(''); }}>恢复所选会话</button></div></VisionDialog>}
    {inspected && <VisionDialog title={`样本检查 · ${stepLabel(inspected.applied_move_index, steps)}`} onClose={props.onCloseReview}>
      <div className="vision-review-body">
        {review ? <><img className="vision-review-image" src={jpeg(review.overlay_jpeg_base64)} alt="真实样本标注叠框" /><div className="vision-review-meta"><span>{review.class_names.map((name, id) => `${name} ${review.boxes.filter((box) => box.class_id === id).length}`).join(' · ')}</span><span>几何 {review.geometry_revision.slice(0, 12)}</span></div></> : <><p role="alert">{reviewFailure?.message}</p><p className="vision-status-note">检查未通过，未生成可用标注叠图。核对真实棋面后可重拍；若源文件损坏，服务会拒绝重拍，请新建会话，不绕过校验。</p></>}
        <p className="vision-status-note">标签来自 SGF 棋面真值。错位、漏灯或坏图须先重拍；不删除后续样本。</p>
        <label className="vision-check"><input type="checkbox" disabled={locked || !captureReady} checked={retakeConfirmed === reviewKey} onChange={(event) => setRetakeConfirmed(event.target.checked ? reviewKey : '')} />需要重拍此帧（保留后续样本）</label>
        <label className="vision-check"><input type="checkbox" disabled={locked || !captureReady} checked={retakeBoardConfirmed === reviewKey} onChange={(event) => setRetakeBoardConfirmed(event.target.checked ? reviewKey : '')} />已重新摆放并核对这帧对应棋面</label>
      </div>
      <div className="vision-review-foot"><span>原图 SHA256 {inspectedSha?.slice(0, 16)} · {inspected.geometry_source}</span><button className="vision-button" type="button" disabled={locked || !captureReady || retakeConfirmed !== reviewKey || retakeBoardConfirmed !== reviewKey} onClick={() => { props.onCapture(inspected.applied_move_index, true); setRetakeConfirmed(''); setRetakeBoardConfirmed(''); }}>确认重拍</button></div>
    </VisionDialog>}
  </main>;
}
