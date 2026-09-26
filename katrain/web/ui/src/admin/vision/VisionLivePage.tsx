import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Activity, Camera, Check, CircleCheck, Info, Layers, RefreshCw, Search, Undo2 } from 'lucide-react';
import VisionDialog from './VisionDialog';
import type { KifuAlbumList, KifuAlbumSummary, VisionAutoCheck, VisionFiducialMode, VisionModels, VisionDevices, VisionFrozen, VisionMode, VisionPreview, VisionReviewFailure, VisionSampleReview, VisionSession, VisionSessionList, VisionStatus, VisionStep } from './types';
import './VisionCapturePage.css';
import './lab.css';

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
  labelPreview: { overlay: VisionSampleReview | null; error: string | null } | null; onLabel: () => void;
  kifu: { query: string; list: KifuAlbumList | null; error: string; loading: boolean };
  onSearchKifu: (query: string) => void; removalLit: string;
  onRemovalGuide: (index: number) => void; onUndo: (frame: string) => void; onEnd: () => void; onLedTest: () => void; onFiducial: (mode: VisionFiducialMode) => void;
  models: VisionModels | null; advance: 'manual' | 'camera'; autoRunning: boolean; autoResult: VisionAutoCheck | null; autoError: string;
  onAdvance: (mode: 'manual' | 'camera') => void; onAutoRunning: (running: boolean) => void; onImportKifu: (id: number, expectedStatus: VisionStatus, expectedContext: number) => void;
};
const modeLabel = (mode?: VisionMode | null) => mode === 'led4' ? '指示灯 · 四类' : mode === 'stones2' ? '无灯 · 双类' : '模式未选择';
const coordinate = (step: VisionStep) => step.col !== null && step.row !== null ? `${'ABCDEFGHJKLMNOPQRST'[step.col]}${19 - step.row}` : '';
const stepLabel = (index: number, steps: VisionStep[]) => {
  if (index === -1) return '初始空盘';
  const step = steps.find((item) => item.move_index === index);
  return step ? `第 ${index + 1} 手 · ${step.color === 'B' ? '黑棋' : '白棋'} ${coordinate(step)}${step.kind === 'setup' ? '（摆子）' : ''}` : `第 ${index + 1} 手`;
};
const rank = (value: string | null) => value ? ` ${value}` : '';
const kifuTitle = (album: KifuAlbumSummary) => [album.event, album.round_name].filter(Boolean).join(' ') || `${album.player_black} 对 ${album.player_white}`;
const point = (item: { row: number; col: number }) => `${'ABCDEFGHJKLMNOPQRST'[item.col]}${19 - item.row}`;
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
  const [mode, setMode] = useState<VisionMode>('led4');
  const [emptyConfirmed, setEmptyConfirmed] = useState('');
  const [boardConfirmed, setBoardConfirmed] = useState('');
  const [geometryConfirmed, setGeometryConfirmed] = useState('');
  const [grid, setGrid] = useState(true);
  const [ledOverlay, setLedOverlay] = useState(true);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState('');
  const [readingFile, setReadingFile] = useState(false);
  const [chooseNew, setChooseNew] = useState(false);
  const [source, setSource] = useState<'search' | 'sgf' | 'resume'>('search');
  const [query, setQuery] = useState('');
  const [albumId, setAlbumId] = useState<number | null>(null);
  const [view, setView] = useState<'raw' | 'warp' | 'label'>('raw');
  const [confirm, setConfirm] = useState<null | 'undo' | 'end' | 'led'>(null);
  const [confirmChecked, setConfirmChecked] = useState(false);
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

  const latestFrame = frames.at(-1)?.frame_id;
  const selectedAlbum = props.kifu.list?.items.find((item) => item.id === albumId);
  const onSearchKifu = props.onSearchKifu;
  const kifuLoaded = props.kifu.list !== null || props.kifu.loading || !!props.kifu.error;
  useEffect(() => { if (source === 'search' && enabled && connected && !kifuLoaded) onSearchKifu(''); }, [source, enabled, connected, kifuLoaded, onSearchKifu]);
  const onLabel = props.onLabel;
  useEffect(() => { if (view === 'label' && latestFrame) onLabel(); }, [view, latestFrame, onLabel]);

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

  const stepState = (n: 1 | 2 | 3 | 4) => {
    const hasSession = !!session && !chooseNew;
    const done = [connected, ready && !geometryChanged, hasSession, hasSession && (next === null || !!session?.ended_at)][n - 1];
    const reachable = [true, connected, connected, !!session][n - 1];
    return done ? 'done' : reachable ? 'current' : 'locked';
  };
  const stepHead = (n: 1 | 2 | 3 | 4, title: string, chip?: ReactNode) => <div className="lab-step-head"><b>{stepState(n) === 'done' ? <Check aria-hidden="true" /> : n}</b>{title}{chip}</div>;
  const headline = !status ? ['正在读取本机状态', ''] : !connected ? [cameraText, cameraState === 'occupied' || cameraState === 'error' ? 'warn' : ''] : status.geometry.state === 'stale' ? ['恢复的标定待复核', 'warn'] : !ready ? ['已连接 · 待标定', 'ok'] : [`Camera ${status.camera.device_id}${status.mode === 'led4' ? ' · 指示灯' : ''} · 标定通过`, 'ok'];
  const nextStepInfo = next !== null && next !== undefined && next >= 0 ? steps.find((item) => item.move_index === next) : undefined;
  const initial = next === -1;
  const led = status?.mode === 'led4';
  const ended = !!session?.ended_at;
  const complete = next === null || ended;
  const removed = nextStepInfo?.removed ?? [];
  const removedText = removed.map((point) => `${'ABCDEFGHJKLMNOPQRST'[point.col]}${19 - point.row}`).join('、');
  const removalPhase = led && !!removed.length && props.removalLit === `${session?.game_id}/${next}`;
  const placed = next === null || next === undefined ? steps.length : Math.max(0, next) + (removalPhase ? 1 : 0);
  const openConfirm = (kind: 'undo' | 'end' | 'led') => { setConfirm(kind); setConfirmChecked(false); };
  const loadedModel = props.models?.models.find((item) => item.id === props.models?.loaded_id);
  const autoReason = status?.fiducial_mode === 'every-move' ? '每手基准点校正开启时不能自动推进：那等于系统自动为几何闪灯。' : !loadedModel ? '需要先在「本机部署与诊断」激活一个已登记的识别模型。' : loadedModel.mode && loadedModel.mode !== session?.mode ? '当前模型的类目与本会话模式不同。' : '';
  const cameraMode = props.advance === 'camera' && !initial;
  const auto = props.autoResult;
  const stalled = auto?.state === 'stalled';
  const label = props.labelPreview;
  const tab = (id: typeof view, text: string, extra?: ReactNode) => <button type="button" role="tab" className="lab-tab" aria-selected={view === id} onClick={() => setView(id)}>{text}{extra}</button>;
  const viewer = () => {
    if (view === 'raw') return raw ? <><div className="cp-figure"><img src={raw} alt="原始相机画面" />{led && ledOverlay && preview?.frame_width && preview.frame_height && !!preview.led_points?.length && <svg className="cp-leds" viewBox={`0 0 ${preview.frame_width} ${preview.frame_height}`} preserveAspectRatio="xMidYMid meet" role="img" aria-label="指示灯位置">{preview.led_points.map((point) => <circle key={`${point.row}-${point.col}`} className={`cp-led-mark ${point.color}`} cx={point.x * preview.frame_width!} cy={point.y * preview.frame_height!} r={preview.frame_width! / 70} />)}</svg>}</div><span className="lab-tag">原始相机画面 · 相机帧 #{preview?.camera_seq}</span>{led && ledOverlay && !!preview?.led_points?.length && <span className="lab-legend"><span>{preview.led_points.map((point) => `${point.color === 'remove' ? '蓝灯' : point.color === 'white' ? '绿灯' : '红灯'} ${'ABCDEFGHJKLMNOPQRST'[point.col]}${19 - point.row}`).join(' · ')}</span></span>}</> : <div className="lab-empty"><Camera aria-hidden="true" /><span>{connected ? '等待新鲜相机帧' : '尚未连接本机摄像头'}</span><small>{connected ? '预览最多 2 帧/秒' : '在右侧第 1 步显式连接；本页不会自动打开设备'}</small></div>;
    if (view === 'warp') return warp ? <><img src={warp} alt="标定后的画面" /><span className="lab-tag">warped 校正 · 几何 {preview?.geometry_revision?.slice(0, 12)} · 同一相机帧</span></> : <div className="lab-empty"><Activity aria-hidden="true" /><span>{!connected ? '尚未连接本机摄像头' : status?.geometry.state === 'required' ? '等待空盘标定' : '等待同帧校正画面'}</span><small>未标定时不生成校正画面</small></div>;
    if (label?.overlay) return <><img src={jpeg(label.overlay.overlay_jpeg_base64)} alt="最新样本标注叠框" /><span className="lab-tag">最新样本 · {stepLabel(label.overlay.applied_move_index, steps)} · 按 SGF 真值自动标注</span><span className="lab-legend">{label.overlay.class_names.map((name, id) => <span key={name}>{name} {label.overlay?.boxes.filter((box) => box.class_id === id).length}</span>)}</span></>;
    return <div className="lab-empty"><Layers aria-hidden="true" /><span>{label?.error ?? (frames.length ? '正在读取最新样本叠框' : '尚无样本')}</span><small>{frames.length ? '标签来自 SGF 棋面真值' : '拍摄第一帧后显示自动标注叠框'}</small></div>;
  };

  return <main className="lab-page vision-live-page" data-camera={cameraState}>
    <div className="lab-heading"><div><h1>采集与数据集</h1><p>Mac 本机 · 指示灯摆谱，采集 YOLO 训练帧</p></div><div className={`lab-status ${headline[1]}`}>{headline[1] === 'ok' && ready ? <CircleCheck aria-hidden="true" /> : <Camera aria-hidden="true" />}{busy ? `${busy}…` : headline[0]}<button className="lab-btn small ghost" type="button" disabled={!!busy || !authorized} onClick={props.onRefresh} aria-label="刷新本机状态"><RefreshCw aria-hidden="true" /></button></div></div>
    <div className="lab-content">
      {status && !status.enabled && <div className="lab-banner info"><Info aria-hidden="true" /><span>此服务未启用本机视觉控制；不会远程打开 Mac 摄像头。</span></div>}
      {(error || fileError) && <div className="lab-banner bad" role="alert"><Info aria-hidden="true" /><span>{error || fileError}</span><button type="button" className="lab-btn small" onClick={props.onRefresh} disabled={!!busy}><RefreshCw aria-hidden="true" />重试读取状态</button></div>}
      {message && <div className="lab-banner ok" role="status"><Check aria-hidden="true" /><span>{message}</span></div>}
      <div className="cp-grid">
        <section className="lab-panel cp-preview" aria-label="采集预览">
          <div className="lab-tabs" role="tablist" aria-label="预览画面">{tab('raw', '原始画面')}{tab('warp', 'warped 校正')}{tab('label', '标注预览', frames.length ? <span className="lab-chip">{frames.length}</span> : null)}</div>
          <div className="lab-viewer cp-viewer">{viewer()}</div>
          {previewError && <p className="cp-preview-error" role="alert">{previewError}</p>}
          <div className="cp-toolbar"><label className="lab-check"><input type="checkbox" checked={grid} onChange={(event) => { setGrid(event.target.checked); if (!event.target.checked) { setGeometryConfirmed(''); props.onPausePreview(false); } }} />显示标定网格</label>{led && <label className="lab-check"><input type="checkbox" checked={ledOverlay} onChange={(event) => setLedOverlay(event.target.checked)} />显示指示灯位置</label>}<span className="cp-spacer" /><span>预览最多 2 帧/秒 · 非训练视频</span></div>
        </section>
        <aside className="lab-panel cp-steps" aria-label="采集步骤">
          <section className={`lab-step ${stepState(1)}`}>{stepHead(1, '连接设备', connected ? <span className="lab-chip ok">已连接</span> : undefined)}<div className="lab-step-body">
            {connected ? <div className="lab-row"><span className="lab-note cp-grow">Camera {status.camera.device_id} · {modeLabel(status.mode)}<br />设备已占用，断开时释放</span>{led && <button className="lab-btn small" type="button" disabled={locked} onClick={() => openConfirm('led')}>测试点亮</button>}<button className="lab-btn small" type="button" disabled={locked || (!!session && !complete && !sessionMismatch)} title={session && !complete && !sessionMismatch ? '采集进行中；先结束本局再断开' : undefined} onClick={props.onDisconnect}>断开连接</button></div> : <>
              <label className="lab-field">摄像头<select value={device} disabled={locked || !devices.length} onChange={(event) => setDevice(Number(event.target.value))}>{devices.length ? devices.map((item) => <option key={item.device_id} value={item.device_id}>{item.label} · 待尝试</option>) : <option value={0}>尚未读取设备候选</option>}</select></label>
              <div className="lab-seg" role="group" aria-label="采集模式"><button type="button" aria-pressed={mode === 'led4'} disabled={locked} onClick={() => setMode('led4')}>指示灯 · 四类</button><button type="button" aria-pressed={mode === 'stones2'} disabled={locked} onClick={() => setMode('stones2')}>无灯 · 双类</button></div>
              <p className="lab-note">{mode === 'led4' ? '类目 black / white / led_red / led_green；使用本机配置的指示灯串口。' : '类目 black / white；不点灯，不伪造 LED 类。'}设备候选不等于可用；占用时不会抢占。</p>
              <button className="lab-btn" type="button" disabled={locked || !devices.length} onClick={() => props.onConnect(device, mode)}>{mode === 'led4' ? '连接摄像头与指示灯' : '连接摄像头'}</button>
            </>}
            {status?.camera.error && <p className="cp-error" role="alert">{status.camera.error}</p>}
            {status?.led.error && <p className="cp-error" role="alert">指示灯：{status.led.error}</p>}
          </div></section>
          <section className={`lab-step ${stepState(2)}`}>{stepHead(2, '空盘标定', ready && !geometryChanged ? <span className="lab-chip ok">{status?.geometry.revision?.slice(0, 8)}</span> : status?.geometry.state === 'stale' ? <span className="lab-chip warn">待复核</span> : undefined)}<div className="lab-step-body">
            {status?.geometry.state === 'stale' ? <>
              <p className="lab-note">恢复的几何待复核；在原始画面上检查网格是否贴合。重连不代表视角未变。</p>
              <label className="lab-check"><input type="checkbox" disabled={locked || !connected || sessionMismatch || !grid || !preview?.geometry_overlay_jpeg_base64 || preview.geometry_revision !== status.geometry.revision} checked={!!preview && geometryConfirmed === preview.frame_id} onChange={(event) => { setGeometryConfirmed(event.target.checked ? preview?.frame_id ?? '' : ''); props.onPausePreview(event.target.checked); }} />已检查当前网格，视角与原标定一致</label>
              <button className="lab-btn" type="button" disabled={locked || !connected || sessionMismatch || !grid || !preview || geometryConfirmed !== preview.frame_id} onClick={() => { if (preview) props.onVerify(preview.frame_id); setGeometryConfirmed(''); }}>确认保存的标定</button>
              <p className="lab-note">视角已变化？清空棋盘后新建标定，再导入新棋谱会话；不覆盖原会话。</p>
            </> : <p className="lab-note">{!connected ? '连接后清空棋盘再标定。' : ready ? `标定通过 · 置信度 ${status?.geometry.confidence?.toFixed(2) ?? '—'}${led && session?.state === 'captured' ? ` · ${status?.fiducial_mode === 'every-move' ? '每手校正' : '不校正'}` : ''}` : `清空棋盘后开始；${status?.mode === 'led4' ? '标定时指示灯全部熄灭。' : '需要看到完整四角。'}`}</p>}
            {led && ready && session?.state !== 'captured' && <label className="lab-field">基准点校正<select value={status?.fiducial_mode ?? 'off'} disabled={locked} onChange={(event) => props.onFiducial(event.target.value as VisionFiducialMode)}><option value="off">关闭（只用开局标定）</option><option value="every-move">每手校正（拍照前点亮空位基准点）</option></select></label>}
            {led && ready && session?.state !== 'captured' && <p className="lab-note">每手校正会在每次拍照前短暂点亮一圈空位基准灯，只在你点拍照时发生。</p>}
            {connected && !(ready && session && !chooseNew) && <label className="lab-check"><input type="checkbox" checked={emptyConfirmed === geometryKey} disabled={locked} onChange={(event) => setEmptyConfirmed(event.target.checked ? geometryKey : '')} />{ready ? '棋盘已清空，需要重新标定' : '棋盘已清空，可开始标定'}</label>}
            {connected && !(ready && session && !chooseNew) && <button className={`lab-btn ${ready ? 'small ghost' : ''}`} type="button" disabled={locked || emptyConfirmed !== geometryKey} onClick={() => { setEmptyConfirmed(''); setBoardConfirmed(''); if (session?.frames.length) { setNeedsNewSession(session.game_id); setChooseNew(true); setFile(null); } props.onCalibrate(); }}>{ready || status?.geometry.state === 'stale' ? '重新空盘标定' : '开始空盘标定'}</button>}
            {status?.geometry.error && <p className="cp-error" role="alert">{status.geometry.error}</p>}
          </div></section>
          <section className={`lab-step ${stepState(3)}`}>{stepHead(3, '选择棋谱', session && !chooseNew ? <span className="lab-chip ok">{session.source?.title ?? session.game_id.slice(0, 8)}</span> : undefined)}<div className="lab-step-body">
            {session && !chooseNew ? <>
              <p className="lab-note">{session.source ? `${session.source.title} · ` : ''}{frames.length} 张样本 · {steps.length} 个 SGF 步骤{skippedPasses > 0 && `（${skippedPasses} 次停着不采帧）`} · 模式与几何在本会话内固定。</p>
              {(complete || sessionMismatch) && <button className="lab-btn small ghost" type="button" disabled={locked} onClick={() => { setChooseNew(true); setFile(null); }}>选择新棋谱</button>}
            </> : <>
              <div className="lab-seg" role="group" aria-label="棋谱来源"><button type="button" aria-pressed={source === 'search'} onClick={() => setSource('search')}>搜索棋谱库</button><button type="button" aria-pressed={source === 'sgf'} onClick={() => setSource('sgf')}>导入 SGF</button><button type="button" aria-pressed={source === 'resume'} onClick={() => setSource('resume')}>恢复会话</button></div>
              {source === 'search' ? <>
                <form className="lab-row" onSubmit={(event) => { event.preventDefault(); setAlbumId(null); props.onSearchKifu(query); }}><label className="lab-field cp-grow">搜索棋谱库<input value={query} maxLength={100} placeholder="棋手、赛事、年份" disabled={!enabled || !connected} onChange={(event) => setQuery(event.target.value)} /></label><button className="lab-btn" type="submit" disabled={!enabled || !connected || props.kifu.loading}><Search aria-hidden="true" />搜索</button></form>
                {props.kifu.error ? <div className="lab-banner bad" role="alert"><Info aria-hidden="true" /><span><strong>棋谱库暂不可用</strong><br />{props.kifu.error}。可改用「导入 SGF」。</span></div>
                  : props.kifu.list?.items.length ? <div className="cp-kifu-list" role="listbox" aria-label="棋谱搜索结果">{props.kifu.list.items.map((album) => <button key={album.id} type="button" role="option" className="cp-kifu" aria-selected={albumId === album.id} disabled={locked} onClick={() => setAlbumId(album.id)}><strong>{kifuTitle(album)}</strong><span>黑 {album.player_black}{rank(album.black_rank)} · 白 {album.player_white}{rank(album.white_rank)}</span><span>{[album.date_played, `${album.move_count} 手`, album.result].filter(Boolean).join(' · ')}</span></button>)}</div>
                  : <p className="lab-note">{props.kifu.loading ? '正在搜索棋谱库…' : !connected ? '连接并标定后可搜索棋谱库。' : props.kifu.list ? '没有匹配的棋谱，换个关键词试试。' : ''}</p>}
                {props.kifu.list && !props.kifu.error && <p className="lab-note">{props.kifu.query ? `「${props.kifu.query}」` : '最新'}共 {props.kifu.list.total} 局{props.kifu.list.total > props.kifu.list.items.length ? `，显示前 ${props.kifu.list.items.length} 局` : ''} · 只列 19 路棋谱</p>}
                <button className="lab-btn primary full" type="button" disabled={locked || !ready || !selectedAlbum} onClick={() => { if (selectedAlbum && status) { props.onImportKifu(selectedAlbum.id, status, props.contextVersion); setChooseNew(false); } }}>{selectedAlbum ? `开始采集 · ${kifuTitle(selectedAlbum)} · ${selectedAlbum.move_count} 手` : '先选择一局棋谱'}</button>
              </> : source === 'sgf' ? <>
                <label className="lab-field">SGF 文件<input type="file" accept=".sgf" disabled={locked} onChange={(event) => {
                  const selected = event.target.files?.[0] ?? null;
                  setFile(selected && selected.size <= 2 * 1024 * 1024 ? selected : null);
                  setFileError(selected && selected.size > 2 * 1024 * 1024 ? 'SGF 文件不能超过 2 MiB。' : '');
                }} /></label>
                <p className="lab-note">只接受 19×19 棋谱；导入时回放校验落子与提子。</p>
                <button className="lab-btn primary full" type="button" disabled={locked || !file || !ready} onClick={() => { void importFile(); }}>{file ? `开始采集 · ${file.name}` : '先选择一份 SGF'}</button>
              </> : <>
                {sessions?.sessions.length ? <div className="cp-kifu-list" role="listbox" aria-label="保存的会话">{sessions.sessions.map((item) => <button key={item.game_id} type="button" role="option" className="cp-kifu" aria-selected={resumeId === item.game_id} disabled={locked || item.state === 'error'} onClick={() => setResumeId(item.game_id)}><strong>{item.source_title ?? `会话 ${item.game_id.slice(0, 12)}`}</strong><span>{item.state === 'error' ? `错误：${item.error}` : `${modeLabel(item.mode)} · 已采 ${item.count ?? 0} 张 · ${item.total_steps ?? 0} 步`}</span></button>)}</div> : <p className="lab-note">{sessions ? '本机没有保存的采集会话。' : '尚未读取会话列表。'}</p>}
                {sessions?.truncated && <p className="lab-note">仅显示前 {sessions.limit} 个会话。</p>}
                <p className="lab-note">恢复不会自动切换设备或模式；恢复后必须复核标定。</p>
                <button className="lab-btn primary full" type="button" disabled={locked || !resumeId} onClick={() => { props.onResume(resumeId); setBoardConfirmed(''); setChooseNew(false); }}>恢复所选会话</button>
              </>}
            </>}
            {sessionMismatch && <p className="cp-error" role="alert">当前设备或模式与原会话不同；请断开后选择 {savedCamera === undefined ? '原摄像头' : `Camera ${savedCamera}`} · {modeLabel(session?.mode)}，或标定并导入新会话。</p>}
          </div></section>
          <section className={`lab-step ${stepState(4)}`}>{stepHead(4, '逐手摆谱采集')}<div className="lab-step-body">
            {geometryChanged || session?.game_id === needsNewSession ? <p className="lab-note">视角已重新标定，请导入新会话。</p> : !session ? <p className="lab-note">先连接、标定并选定棋谱。</p> : <>
              <div className="cp-next">{complete ? <><span className="cp-stone done" /><strong>本局采集完成</strong><span>共 {frames.length} 帧{ended ? ' · 已手动结束' : ''} · 可在下方检查并冻结</span></> : initial ? <><span className="cp-stone empty" /><strong>拍摄初始帧</strong><span>{led ? '空盘 + 第 1 手指示灯' : '清空棋盘，保存真实负样本'}；随后按 SGF 摆谱</span></> : removalPhase ? <><span className="cp-stone remove" /><strong>提走 {removed.length} 子：{removedText}</strong><span>第 {(next ?? 0) + 1} 手提子 · 蓝灯位置取走棋子后拍照</span></> : <><span className={`cp-stone ${nextStepInfo?.color ?? ''}`} /><strong>{stepLabel(next ?? -1, steps)}</strong><span>{led ? `${nextStepInfo?.color === 'W' ? '绿灯' : '红灯'}指示 ${nextStepInfo ? coordinate(nextStepInfo) : ''} · 按灯位摆放` : `按 SGF 摆放 ${nextStepInfo ? coordinate(nextStepInfo) : ''}`}{removed.length ? (led ? ' · 落子后需提子' : ` · 同时提走 ${removedText}`) : ''}</span></>}</div>
              {led && !complete && !initial && <div className="cp-led-line">{removalPhase ? <><span className="cp-led blue" />蓝灯：需提走的子</> : <><span className={`cp-led ${nextStepInfo?.color === 'W' ? 'green' : 'red'}`} />{nextStepInfo?.color === 'W' ? '绿灯 = 下一手白棋' : '红灯 = 下一手黑棋'}</>}{status?.fiducial_mode === 'every-move' ? ' · 每手基准点校正' : ''}</div>}
              <div className="cp-progress" aria-label="采集进度"><i style={{ width: `${steps.length ? Math.round((placed / steps.length) * 100) : 0}%` }} /></div>
              <div className="lab-note">已摆 {placed} / {steps.length} 手 · 已采 {frames.length} 帧 · 会话 {session.game_id.slice(0, 12)}</div>
              {!complete && !initial && <div className="lab-seg" role="group" aria-label="推进方式"><button type="button" aria-pressed={props.advance === 'manual'} disabled={locked} onClick={() => props.onAdvance('manual')}>手动确认</button><button type="button" aria-pressed={props.advance === 'camera'} disabled={locked || !!autoReason} title={autoReason || undefined} onClick={() => props.onAdvance('camera')}>摄像头自动推进</button></div>}
              {!complete && !initial && autoReason && props.advance === 'manual' && <p className="lab-note">{autoReason}</p>}
              {!complete && cameraMode && <div className={`lab-banner ${stalled ? '' : 'info'}`} role="status"><Camera aria-hidden="true" /><span>{!props.autoRunning ? '自动推进已暂停。' : !auto ? '正在用当前模型识别棋面…' : auto.state === 'matching' ? `棋面一致 · 稳定 ${auto.stable_frames}/${auto.required_frames} 帧 · ${(auto.stable_ms / 1000).toFixed(1)}/${(auto.required_ms / 1000).toFixed(1)} 秒` : `${stalled ? '一直不一致，可人工确认。' : '等待棋面一致。'}${auto.missing.length ? `缺/错：${auto.missing.map(point).join('、')}。` : ''}${auto.extra.length ? `多出：${auto.extra.map(point).join('、')}。` : ''}`}<br /><small>模型 {loadedModel?.id.slice(6, 18)} · 完全一致且稳定 1 秒才拍，拍后再核对一次</small></span><button type="button" className="lab-btn small" disabled={locked} onClick={() => props.onAutoRunning(!props.autoRunning)}>{props.autoRunning ? '暂停' : '继续'}</button></div>}
              {!complete && props.autoError && <p className="cp-error" role="alert">自动推进已暂停：{props.autoError}</p>}
              {!complete && (led && removed.length && !removalPhase && !initial ? <>
                <label className="lab-check"><input type="checkbox" checked={boardConfirmed === boardKey} disabled={locked || !captureReady} onChange={(event) => setBoardConfirmed(event.target.checked ? boardKey : '')} />已按灯位落下 {nextStepInfo ? coordinate(nextStepInfo) : ''}，还没提子</label>
                <button className="lab-btn primary full" type="button" disabled={locked || !captureReady || boardConfirmed !== boardKey} onClick={() => { if (next !== null && next !== undefined) props.onRemovalGuide(next); setBoardConfirmed(''); }}>{busy === '点亮提子位置' ? '正在点亮蓝灯…' : '已落子 · 点亮提子位置'}</button>
              </> : (!cameraMode || stalled || !props.autoRunning) && <>
                <label className="lab-check"><input type="checkbox" checked={boardConfirmed === boardKey} disabled={locked || !captureReady} onChange={(event) => setBoardConfirmed(event.target.checked ? boardKey : '')} />{initial ? (led ? '棋盘已清空，只有指示灯亮着' : '棋盘已清空') : removalPhase ? '已取走蓝灯位置的棋子，棋面与 SGF 一致' : led ? '已按灯位摆好，棋面与 SGF 一致' : removed.length ? '已落子并提走棋子，棋面与 SGF 一致' : '已按 SGF 摆好，棋面一致'}</label>
                <button className="lab-btn primary full" type="button" disabled={locked || !captureReady || next === undefined || boardConfirmed !== boardKey} onClick={() => { if (next !== null && next !== undefined) props.onCapture(next); setBoardConfirmed(''); }}>{busy === '采集当前手' ? (led ? '等待指示灯稳定后抓帧…' : '正在抓取新鲜相机帧…') : initial ? '拍摄初始帧' : removalPhase ? '已提子 · 拍照' : '已摆好 · 拍照并进入下一手'}</button>
              </>)}
              {!ended && frames.length > 0 && <div className="lab-row"><button className="lab-btn small ghost" type="button" disabled={locked || frames.length < 2} onClick={() => openConfirm('undo')}><Undo2 aria-hidden="true" />撤回上一帧</button><button className="lab-btn small ghost" type="button" disabled={locked} onClick={() => openConfirm('end')}>结束本局</button></div>}
            </>}
          </div></section>
        </aside>
      </div>
      <section className="lab-panel cp-dataset" aria-label="数据集草稿"><div className="lab-panel-head"><h2>数据集草稿</h2><small>检查叠框 → 冻结版本 → 上传测试机</small></div><div className="cp-dataset-body">
        {frames.length ? <>
          <div className="cp-meta">{session?.source && <span>棋谱 <strong>{session.source.title}</strong></span>}<span>会话 <strong>{session?.game_id.slice(0, 12)}</strong></span><span>模式 <strong>{modeLabel(session?.mode)}</strong></span><span>几何 <strong>{session?.geometry_revision.slice(0, 8)}</strong></span><span>已采 <strong>{frames.length}</strong> 帧</span><span>训练 / 验证按 SGF 时间段划分，不随机拆连续帧</span></div>
          <div className="cp-samples" aria-label="已采集样本">{frames.slice().reverse().map((frame) => <button key={frame.frame_id} className="cp-sample" type="button" disabled={locked} onClick={() => props.onReview(frame.frame_id)}><strong>{stepLabel(frame.applied_move_index, steps)}</strong><span>帧 #{frame.camera_seq} · 查看标签</span></button>)}</div>
        </> : <p className="lab-note">还没有采集样本。开始会话后，每拍一帧都会按 SGF 真值自动生成标注。</p>}
        <div className="cp-actions"><button className="lab-btn primary" type="button" disabled={locked || frames.length < 2} onClick={props.onFreeze}>{busy === '冻结数据集' ? '正在冻结…' : '冻结数据集版本'}</button><button className="lab-btn" type="button" disabled>上传测试机 · 待授权</button><span className="lab-note">{frozenId ? `版本 ${frozenId}${frozen ? ` · 清单 SHA256 ${frozen.manifest_sha256.slice(0, 16)}` : ''} · 只读，待上传` : frames.length ? '冻结会校验每张图、标签、类目和文件 SHA-256，冻结后只读；失败保留原文件。' : ''}</span></div>
      </div></section>
      <p className="lab-foot">相机与训练帧仅在本机；离开页面不会断开设备，请手动断开。冻结为同步操作，请等待校验完成。</p>
    </div>
    {confirm && <VisionDialog title={confirm === 'undo' ? '撤回上一帧' : confirm === 'end' ? '结束本局采集' : '测试点亮指示灯'} onClose={() => setConfirm(null)}>
      <div className="vision-review-body">
        <p>{confirm === 'undo' ? `撤回最近一帧（${frames.length ? stepLabel(frames[frames.length - 1].applied_move_index, steps) : ''}），回到它之前的棋面。已写入的图片留在会话目录，清单不再引用它。` : confirm === 'end' ? `已采 ${frames.length} 帧。结束后不能继续追加或撤回，可检查并冻结。` : '依次点亮四个角和天元各 1 秒，用来确认串口与灯位映射。测试期间不拍照，结束后恢复当前引导灯。'}</p>
        {confirm === 'undo' && <label className="vision-check"><input type="checkbox" checked={confirmChecked} onChange={(event) => setConfirmChecked(event.target.checked)} />我会把棋盘恢复到上一帧的棋面。</label>}
      </div>
      <div className="vision-review-foot"><span /><button className="vision-button" type="button" disabled={locked || (confirm === 'undo' && !confirmChecked)} onClick={() => { const kind = confirm; setConfirm(null); if (kind === 'undo') { const last = frames.at(-1); if (last) props.onUndo(last.frame_id); } else if (kind === 'end') props.onEnd(); else props.onLedTest(); }}>{confirm === 'undo' ? '撤回' : confirm === 'end' ? '结束本局' : '开始测试'}</button></div>
    </VisionDialog>}
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
