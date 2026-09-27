import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Copy, Database, Info } from 'lucide-react';
import type { ArtifactImage, ArtifactLink, ArtifactListing, createAdminApi } from '../api/client';
import { describe, Dialog, LoadError, when } from '../users/shared';
import '../vision/lab.css';
import '../users/UsersPage.css';
import './ArtifactsPage.css';

type Props = { api: ReturnType<typeof createAdminApi>; production: boolean; onUnauthorized: () => void };
type Status = 'candidate' | 'released' | 'revoked';
const STATUS: Record<Status, [string, string]> = { candidate: ['info', '候选'], released: ['ok', '已发布'], revoked: ['bad', '已撤回'] };
const VERB: Record<Status, string> = { candidate: '设为候选', released: '发布', revoked: '撤回' };
const size = (bytes: number | null | undefined) => !bytes ? '—' : bytes >= 1e9 ? `${(bytes / 1e9).toFixed(2)} GB` : `${(bytes / 1e6).toFixed(1)} MB`;
const shortHash = (hash: unknown) => typeof hash === 'string' && hash.length >= 8 ? `${hash.slice(0, 4)}…${hash.slice(-4)}` : '—';

export default function ArtifactsPage({ api, production, onUnauthorized }: Props) {
  const [data, setData] = useState<ArtifactListing | null>(null);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  const [changing, setChanging] = useState<{ image: ArtifactImage; to: Status } | null>(null);
  const [link, setLink] = useState<(ArtifactLink & { label: string }) | null>(null);
  const [linkBusy, setLinkBusy] = useState('');
  const [copied, setCopied] = useState('');
  const unauthorized = useRef(onUnauthorized);
  useEffect(() => { unauthorized.current = onUnauthorized; }, [onUnauthorized]);
  const failed = useCallback((cause: unknown, set: (message: string) => void) => {
    if (cause instanceof DOMException && cause.name === 'AbortError') return;
    const { status, message } = describe(cause);
    if (status === 401) unauthorized.current(); else set(message);
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setError('');
    api.artifacts(controller.signal).then((next) => {
      if (!Array.isArray(next?.images)) throw new Error('服务返回的镜像列表格式不对');
      setData(next);
    }).catch((cause) => failed(cause, setError));
    return () => controller.abort();
  }, [api, attempt, failed]);

  const makeLink = async (image: ArtifactImage) => {
    setLinkBusy(image.prefix); setError(''); setCopied('');
    try { setLink({ ...(await api.artifactLink(image.prefix)), label: `${image.manifest?.board ?? ''} ${image.manifest?.version ?? image.prefix}` }); } catch (cause) { failed(cause, setError); }
    setLinkBusy('');
  };
  const copy = (text: string) => { navigator.clipboard?.writeText(text).then(() => setCopied('已复制')).catch(() => setCopied('复制失败，请手动选中')); };
  const heading = <div className="lab-heading"><div><h1>金镜像</h1><p>盒子出厂系统镜像：登记、发布与签名下载，不在后台上传或删除</p></div><span className="lab-status"><Info aria-hidden="true" />{data?.bucket ? `私有桶 ${data.bucket} · ` : ''}链接 12 小时有效</span></div>;
  if (data && data.state !== 'configured') {
    return <main className="lab-page ub-page ar-page">{heading}<div className="lab-content"><section className="lab-panel"><div className="lab-empty">
      {data.state === 'unconfigured' ? <><Database aria-hidden="true" /><span>制品库尚未配置</span><small>在后台进程环境里设置 KATRAIN_ARTIFACTS_S3_ENDPOINT、KATRAIN_ARTIFACTS_ACCESS_KEY / SECRET_KEY（只读账号）与 KATRAIN_ARTIFACTS_PUBLIC_ENDPOINT 后重启。</small></>
        : <><AlertTriangle aria-hidden="true" /><span>连不上制品库（{data.error}）</span><small>桶 {data.bucket} 暂时读不到，列表不代表没有镜像。</small><button className="lab-btn small" type="button" onClick={() => setAttempt((n) => n + 1)}>重试</button></>}
    </div></section></div></main>;
  }
  return <main className="lab-page ub-page ar-page">
    {heading}
    <div className="lab-content">
      {error && <LoadError message={error} onRetry={() => setAttempt((n) => n + 1)} />}
      {link && <section className="lab-panel ar-link" aria-label="下载链接">
        <div className="lab-panel-head"><h2>下载链接 · {link.label}</h2><small>{when(link.expires_at)} 前有效 · 生成动作已写入审计</small></div>
        <div className="ar-link-body"><code className="mono">{link.url}</code><button className="lab-btn small" type="button" onClick={() => copy(link.url)}><Copy aria-hidden="true" />复制</button>{copied && <span className="lab-note" role="status">{copied}</span>}</div>
        <p className="lab-note ar-pad">下载后用 sha256 核对：<b className="mono">{link.sha256}</b></p>
      </section>}
      <section className="lab-panel" aria-labelledby="ar-title">
        <div className="lab-panel-head"><h2 id="ar-title">镜像</h2><small>{data ? `${data.images.length} 个${data.truncated ? '（只列前 500 个）' : ''} · 上传只走 provisioning 脚本` : '读取中'}</small></div>
        <div className="ub-lhead ar"><span>板型</span><span>版本</span><span>文件</span><span className="num">大小</span><span>sha256</span><span>上传</span><span>状态</span><span /></div>
        {data?.images.map((image) => { const status = (image.status ?? 'candidate') as Status; const [tone, label] = STATUS[status] ?? ['', status]; const broken = image.problems.length > 0; const m = image.manifest; return <div key={image.prefix} className={`ub-lrow ar ${broken ? 'bad' : ''}`}>
          <span>{m?.board ?? '—'}</span><span className="mono">{m?.version ?? '—'}</span>
          <span className="mono ar-file">{m?.file ?? image.prefix}{broken && <small className="ar-prob"><AlertTriangle aria-hidden="true" />{image.problems.join('；')}</small>}</span>
          <span className="num">{size(image.object_size)}</span><span className="mono muted" title={typeof m?.sha256 === 'string' ? m.sha256 : undefined}>{shortHash(m?.sha256)}</span>
          <span className="muted">{m?.uploaded_by ?? '—'}<small>{typeof m?.uploaded_at === 'string' ? when(m.uploaded_at) : '—'}</small></span>
          <span><span className={`lab-chip ${tone}`} title={image.status_note ?? undefined}>{label}</span></span>
          <span className="ar-act">{status === 'revoked' ? <button className="lab-btn small" type="button" onClick={() => setChanging({ image, to: 'candidate' })}>设为候选</button>
            : status === 'released' ? <><button className="lab-btn small" type="button" onClick={() => setChanging({ image, to: 'revoked' })}>撤回</button><button className="lab-btn small" type="button" disabled={linkBusy === image.prefix} onClick={() => { void makeLink(image); }}>下载链接</button></>
            : <><button className="lab-btn small primary" type="button" disabled={broken} onClick={() => setChanging({ image, to: 'released' })}>发布</button><button className="lab-btn small" type="button" disabled={broken || linkBusy === image.prefix} onClick={() => { void makeLink(image); }}>下载链接</button></>}</span>
        </div>; })}
        {data && !data.images.length && <div className="lab-empty"><small>桶里还没有镜像。用 provisioning 脚本上传后会出现在这里。</small></div>}
        {!data && !error && <div className="lab-empty"><small>正在读取镜像</small></div>}
      </section>
      <p className="lab-note">已撤回的镜像不再提供下载链接；manifest 有问题的镜像不能发布。状态变更与生成链接都写入审计。</p>
    </div>
    {changing && <StatusDialog api={api} production={production} {...changing} onClose={() => setChanging(null)} onDone={() => { setChanging(null); setAttempt((n) => n + 1); }} onUnauthorized={() => unauthorized.current()} />}
  </main>;
}

function StatusDialog({ api, image, to, production, onClose, onDone, onUnauthorized }: { api: ReturnType<typeof createAdminApi>; image: ArtifactImage; to: Status; production: boolean; onClose: () => void; onDone: () => void; onUnauthorized: () => void }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const label = `${image.manifest?.board ?? ''} ${image.manifest?.version ?? image.prefix}`;
  const submit = async () => {
    setBusy(true); setError('');
    try { await api.artifactStatus(image.prefix, to, note.trim()); onDone(); } catch (cause) {
      const { status, message } = describe(cause);
      if (status === 401) onUnauthorized(); else setError(message);
      setBusy(false);
    }
  };
  return <Dialog label={`${VERB[to]} ${label}`} title={<>{VERB[to]} {label}{production && <span className="lab-chip bad">生产环境</span>}</>} onClose={onClose} closable={!busy}
    actions={<><button className="lab-btn" type="button" disabled={busy} onClick={onClose}>返回</button><button className={`lab-btn ${to === 'released' ? 'primary' : ''}`} type="button" disabled={busy || note.trim().length < 5} onClick={() => { void submit(); }}>{busy ? '提交中' : `确认${VERB[to]}`}</button></>}>
    <p className="lab-note">{to === 'released' ? '发布后产线按这个版本刷机。' : to === 'revoked' ? '撤回后不再提供下载链接；已刷过的盒子不受影响。' : '回到候选：不再作为发布版本，但仍可下载核对。'}操作会写入审计。</p>
    <label className="lab-field">原因（至少 5 个字）<input value={note} maxLength={200} onChange={(event) => setNote(event.target.value)} /></label>
    {error && <LoadError message={error} />}
  </Dialog>;
}
